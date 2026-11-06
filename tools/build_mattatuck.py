#!/usr/bin/env python3
"""Build the Mattatuck Museum (Waterbury, CT) map guide (run: python3 tools/build_mattatuck.py).

    data/mattatuck/floors.json     the Main Floor, 2nd Floor and 3rd Floor seen from above (flat 2D)
    data/mattatuck/artworks.json   the shows on view and the collection, each in a gallery
    data/guides/Q6789613.json      the same, for the museum page

First run tools/harvest_mattatuck.py (list, then detail): it reads the museum's catalogue on Connecticut Collections
into .cache/mattatuck. The museum's own pages (visit, exhibitions, collections, rentals) are read once into the same
folder by this script.

The map
-------
The Mattatuck publishes no floor plan (none on mattmuseum.org, in its PDFs or in the architects' pages; its 3D tours
are Matterport scans of past shows). The plan here is APPROXIMATE, drawn inside the building's real outline:
  - OpenStreetMap way 467492386 (ODbL): the 1912 Masonic Temple (west wing, on West Main Street facing the Green) and
    the wing along the north (towards Park Place); the plaza and sculpture garden at the corner of West Main Street and
    Park Place, where the old addition was taken down in 2019-21 (Ann Beha Architects, now Annum Architects).
  - the museum's own words: the Foyer "on the main floor" with large windows on the Green (welcome desk, shop, the Art
    of Yum café in the lobby); the History Gallery (Orton P. Camp Jr. History Exhibit, 5,050 sq ft) on the first floor;
    the art galleries (6,645 sq ft: Upson Gallery for the collection, the Whittemore and Noonan, Munger and Baker
    Galleries for shows) upstairs, with windows on the Green; the Performing Arts Center "on the 3rd floor", with views
    of the Green; the Monteiro Family Community Gallery "on the Museum's 3rd floor"; the Button Gallery on the top floor;
    the Rooftop Terrace (3,300 sq ft) on the new addition, seen from above by visitors upstairs; classrooms on the
    ground and mezzanine levels; free parking in the lots on Park Place (GPS 26 Park Place).
Which room is where inside each wing, and which floor each gallery is on, is our best reading of those sources; the
map and each work say so. Coordinates are metres east / north of the middle of the building (OpenStreetMap), times K.
"""
import html
import io
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'mattatuck'
CACHE = ROOT / '.cache' / 'mattatuck'
MUSEUM = 'Q6789613'
NAME = 'Mattatuck Museum'
SITE = 'https://www.mattmuseum.org'
CTC = 'https://ctcollections.org/index.php'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
K = 12          # map units per metre


def P(x, y):
    """Metres east / north of the building's middle -> map units (north up)."""
    return [round((x + 45) * K, 1), round((55 - y) * K, 1)]


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def band(pts, half):
    import math
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1
        left.append((x - dy / n * half, y + dx / n * half)); right.append((x + dy / n * half, y - dx / n * half))
    return left + right[::-1]


# The building (OpenStreetMap way 467492386), metres from its middle (41.557333 N, 73.043259 W)
BUILDING = [(-7.2, 12.0), (-6.4, 14.5), (-5.4, 14.3), (-0.3, 33.9), (31.9, 25.9), (26.4, 5.8), (13.2, 9.1),
            (12.4, 6.1), (12.5, 0.8), (12.7, -7.3), (13.1, -17.8), (4.9, -15.8), (-4.3, -14.9), (-5.6, -16.4),
            (-7.5, -16.0), (-9.5, -15.5), (-13.4, -14.5), (-13.2, -13.9), (-11.7, -7.8), (-10.9, -4.5), (-9.8, -4.8),
            (-6.7, 7.2), (-8.2, 7.8)]


def clip(poly, box):
    """The part of poly inside the rectangle box (Sutherland-Hodgman; the box is convex)."""
    x0, y0, x1, y1 = box
    edges = [(lambda p: p[0] >= x0, lambda a, b: (x0, a[1] + (b[1] - a[1]) * (x0 - a[0]) / (b[0] - a[0]))),
             (lambda p: p[0] <= x1, lambda a, b: (x1, a[1] + (b[1] - a[1]) * (x1 - a[0]) / (b[0] - a[0]))),
             (lambda p: p[1] >= y0, lambda a, b: (a[0] + (b[0] - a[0]) * (y0 - a[1]) / (b[1] - a[1]), y0)),
             (lambda p: p[1] <= y1, lambda a, b: (a[0] + (b[0] - a[0]) * (y1 - a[1]) / (b[1] - a[1]), y1))]
    out = list(poly)
    for inside, cut in edges:
        src, out = out, []
        for i, cur in enumerate(src):
            prev = src[i - 1]
            if inside(cur):
                if not inside(prev): out.append(cut(prev, cur))
                out.append(cur)
            elif inside(prev):
                out.append(cut(prev, cur))
    pts = []
    for p in out:
        p = (round(p[0], 2), round(p[1], 2))
        if not pts or p != pts[-1]: pts.append(p)
    return pts


def B(x0, y0, x1, y1):
    return clip(BUILDING, (x0, y0, x1, y1))


PLAZA = [(13.1, -17.8), (12.7, -7.3), (12.5, 0.8), (12.4, 6.1), (13.2, 9.1), (26.4, 5.8), (24.8, -2.5),
         (20.5, -21.5), (13.0, -19.8)]
WEST_MAIN = band([(-22, -17), (-10, -21.5), (20, -30), (30, -33.5)], 5)
PARK_PLACE = band([(23, -29), (28, -10), (34, 15), (39, 36), (41, 48)], 3.5)
SIDEWALK = band([(-20, -14.3), (-14, -17.5), (13, -21.5), (20, -24)], 1.6)
LOT = [(7, 52), (34, 46), (30, 28), (3, 35)]

# rooms: (id, kind, name, polygon, short label for galleries)
F1 = [
    ('West Main Street', 'corridor', 'West Main Street, on the north-west corner of the Waterbury Green', WEST_MAIN,
     None),
    ('Park Place', 'corridor', 'Park Place: turn in here for the museum’s free parking lots', PARK_PLACE, None),
    ('Sidewalk', 'corridor', 'Sidewalk along West Main Street (large windows show the shows inside)', SIDEWALK, None),
    ('Plaza', 'space', 'Plaza and sculpture garden on the corner of West Main Street and Park Place: the way in',
     PLAZA, None),
    ('Parking Lot', 'space', 'Museum parking on Park Place: free (more in the large lot past the YMCA play area and '
     'the Gaffney Place lot; GPS 26 Park Place). Four EV charging spaces, free for members', LOT, None),
    ('Foyer', 'corridor', 'The Foyer (lobby): Welcome Desk for tickets, maps and the wheelchair, large windows on the '
     'Green', B(-3, -19, 14, 0), None),
    ('Museum Shop', 'space', 'Museum Shop (books on the collection, Waterbury gifts)', B(-14, -19, -3, -8), None),
    ('Coat Room', 'space', 'Coat room: backpacks, large bags and big umbrellas go here (locking cubbies); the '
     'wheelchair to borrow', B(-14, -8, -3, 0), None),
    ('Restrooms', 'space', 'Restrooms (accessible)', B(-14, 0, 3, 6), None),
    ('Studio', 'space', 'Classrooms and studio (programs, workshops, School’s OUT!)', B(-14, 6, 3, 15), None),
    ('Elevator Hall', 'corridor', 'Hall to the elevator and stairs', B(3, 0, 14, 15), None),
    ('Art of Yum Café', 'space', 'Art of Yum Café: lunch, coffee and treats. Food and drink only here and on the '
     'Rooftop Terrace', B(14, 4, 34, 15), None),
    ('History Gallery', 'gallery', 'History Gallery: Waterbury, a City of Transitions (Orton P. Camp Jr. History '
     'Exhibit), Meet Fortune, and history shows', B(-8, 15, 34, 36), 'History'),
]
F1_DOORS = [('Foyer', 'Plaza', (12.8, -9)), ('Foyer', 'Museum Shop', (-3, -13)), ('Foyer', 'Coat Room', (-3, -4)),
            ('Foyer', 'Restrooms', (0, 0)), ('Foyer', 'Elevator Hall', (8, 0)), ('Elevator Hall', 'Studio', (3, 10)),
            ('Elevator Hall', 'Art of Yum Café', (14, 11)), ('Elevator Hall', 'History Gallery', (8, 15)),
            ('Art of Yum Café', 'History Gallery', (24, 15)), ('Plaza', 'Sidewalk', (16, -22)),
            ('Plaza', 'Park Place', (25, 0)), ('Park Place', 'West Main Street', (21, -31)),
            ('Sidewalk', 'West Main Street', (-20, -17.5)), ('Park Place', 'Parking Lot', (32, 38))]
F1_AMEN = [('entrance', 12.6, -9), ('info', 5, -9), ('shop', -8, -14), ('coat', -8, -4), ('restroom', -5.5, 3),
           ('restroom-all', -1, 3), ('elevator', 9, 9), ('stairs', 5, 3), ('dining', 24, 10), ('parking', 18, 40)]
F1_LABELS = [('Waterbury Green ↓ (Civil War monument)', 0, -33),
             ('Entrance from the plaza ←', 19, -12),
             ('Accessible: entrances, elevators, galleries and restrooms', -2, 40)]

F2 = [
    ('Gallery Hall', 'corridor', 'Upstairs hall at the top of the stairs', B(-14, -2, 14, 4), None),
    ('Whittemore Gallery', 'gallery', 'Whittemore Gallery (special exhibitions, windows on the Green)',
     B(-14, -19, 0, -2), 'Whittemore'),
    ('Noonan Gallery', 'gallery', 'Noonan Gallery (special exhibitions, windows on the Green)', B(0, -19, 14, -2),
     'Noonan'),
    ('Munger Gallery', 'gallery', 'Munger Gallery (special exhibitions)', B(-14, 4, 3, 15), 'Munger'),
    ('Elevator Lobby', 'corridor', 'Elevator lobby (a big painting from the collection usually greets you here)',
     B(3, 4, 14, 15), None),
    ('Rooftop Terrace', 'space', 'Rooftop Terrace, 3,300 sq ft over the Green: open in good weather; food and drink '
     'allowed here', B(14, 4, 34, 15), None),
    ('Upson Gallery', 'gallery', 'Upson Gallery: the Mattatuck Museum Collection (American art, Connecticut artists)',
     B(-8, 15, 20, 36), 'Upson'),
    ('Baker Gallery', 'gallery', 'Baker Gallery (special exhibitions)', B(20, 15, 34, 36), 'Baker'),
]
F2_DOORS = [('Gallery Hall', 'Whittemore Gallery', (-7, -2)), ('Gallery Hall', 'Noonan Gallery', (7, -2)),
            ('Whittemore Gallery', 'Noonan Gallery', (0, -10)), ('Gallery Hall', 'Munger Gallery', (-5, 4)),
            ('Gallery Hall', 'Elevator Lobby', (8, 4)), ('Elevator Lobby', 'Munger Gallery', (3, 10)),
            ('Elevator Lobby', 'Upson Gallery', (8, 15)), ('Upson Gallery', 'Baker Gallery', (20, 24)),
            ('Elevator Lobby', 'Rooftop Terrace', (14, 11))]
F2_AMEN = [('elevator', 9, 9), ('stairs', 5, 3)]
F2_LABELS = [('2nd floor: approximate plan (no plan is published)', 5, -24)]

F3 = [
    ('Upper Hall', 'corridor', '3rd floor hall', B(-14, 2, 14, 8), None),
    ('Performing Arts Center', 'space', 'Performing Arts Center: the old Masonic hall, mahogany panelling and views of '
     'the Green (concerts, talks, events)', B(-14, -19, 14, 2), None),
    ('Community Gallery', 'gallery', 'Monteiro Family Community Gallery: art and history from Waterbury-area schools '
     'and community groups', B(-14, 8, 3, 15), 'Community'),
    ('Top Elevator Lobby', 'corridor', 'Elevator lobby (looks down onto the Rooftop Terrace)', B(3, 8, 14, 15), None),
    ('Button Gallery', 'gallery', 'Button Gallery: the Waterbury Button Museum, more than 10,000 buttons on show',
     B(-8, 15, 34, 36), 'Buttons'),
]
F3_DOORS = [('Upper Hall', 'Performing Arts Center', (0, 2)), ('Upper Hall', 'Community Gallery', (-5, 8)),
            ('Upper Hall', 'Top Elevator Lobby', (8, 8)), ('Top Elevator Lobby', 'Button Gallery', (8, 15)),
            ('Top Elevator Lobby', 'Community Gallery', (3, 11))]
F3_AMEN = [('elevator', 9, 9), ('stairs', 5, 3)]
F3_LABELS = [('Rooftop Terrace below (2nd floor)', 24, 10), ('3rd floor: approximate plan (no plan is published)', 5, -24)]


def inside(pt, poly):
    x, y = pt
    c = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c


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


def build_floors():
    floors = [
        floor('1', 'Main Floor', 0, 'Entrance from the plaza · Foyer · Welcome Desk · Shop · Art of Yum Café · '
              'Restrooms · History Gallery', F1, F1_DOORS, F1_AMEN, F1_LABELS),
        floor('2', '2nd Floor', 1, 'Upson Gallery (the collection) · Whittemore, Noonan, Munger and Baker Galleries · '
              'Rooftop Terrace', F2, F2_DOORS, F2_AMEN, F2_LABELS),
        floor('3', '3rd Floor', 2, 'Button Gallery · Community Gallery · Performing Arts Center', F3, F3_DOORS,
              F3_AMEN, F3_LABELS),
    ]
    for f in floors:
        ids = [r['id'] for r in f['rooms']]
        assert len(ids) == len(set(ids)), f['id']
        for d in f['doors']:
            assert d['a'] in ids and d['b'] in ids, (f['id'], d)
        for a in f['amenities']:
            assert any(inside(a['at'], r['poly']) for r in f['rooms']), (f['id'], a)
    return {'about': 'Built by tools/build_mattatuck.py. The Mattatuck publishes no floor plan: this one is '
                     'approximate, drawn inside the building’s real outline (OpenStreetMap) from the museum’s own '
                     'descriptions of its rooms (Foyer, café and History Gallery on the main floor, art galleries and '
                     'Rooftop Terrace upstairs, Performing Arts Center, Community Gallery and buttons on the 3rd '
                     'floor).',
            'source': 'Approximate: OpenStreetMap building outline and the Mattatuck Museum’s visit, rental, '
                      'exhibition and collection pages',
            'units': f'metres x {K}, north up', 'approximate': True, 'defaultFloor': '1', 'galleryWord': 'Gallery',
            'floors': floors}


# ---- the museum's own pages ------------------------------------------------------------------------------------------

def page(path):
    dest = CACHE / 'pages' / (path.strip('/').replace('/', '_') + '.html')
    if not (dest.exists() and dest.stat().st_size > 500):
        dest.parent.mkdir(parents=True, exist_ok=True)
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '90', '-A', UA, f'{SITE}/{path.strip("/")}/'],
                             capture_output=True).stdout
        time.sleep(3)
        if not out: return ''
        dest.write_bytes(out)
    return dest.read_text(encoding='utf-8', errors='ignore')


def text_of(s):
    m = re.search(r'(?s)<main.*?</main>', s)
    s = m.group(0) if m else s
    s = re.sub(r'(?s)<(script|style|noscript|svg|nav|header|footer)[^>]*>.*?</\1>', '', s)
    s = re.sub(r'<br\s*/?>|</p>|</h\d>|</li>|</div>', '\n', s)
    t = html.unescape(re.sub(r'<[^>]+>', '', s))
    return [l.strip() for l in t.split('\n') if l.strip()]


def picture(key, url):
    """The museum's own picture of a show or gallery, made smaller for phones (cached)."""
    from PIL import Image
    dest = OUT / 'images' / f'{key}.jpg'
    if dest.exists(): return f'data/mattatuck/images/{key}.jpg'
    raw = CACHE / 'img' / f'{key}.bin'
    if not raw.exists():
        raw.parent.mkdir(parents=True, exist_ok=True)
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '90', '-A', UA, url], capture_output=True).stdout
        time.sleep(3)
        if not out: return None
        raw.write_bytes(out)
    im = Image.open(io.BytesIO(raw.read_bytes()))
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA'); bg = Image.new('RGB', im.size, 'white'); bg.paste(im, mask=im.split()[-1]); im = bg
    im = im.convert('RGB'); im.thumbnail((1000, 1000))
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)
    return f'data/mattatuck/images/{key}.jpg'


UP = SITE + '/wp-content/uploads/'
# the shows on view and the permanent galleries (mattmuseum.org, read Nov 5, 2026)
# id, title, artist, date, gallery, page, picture, text, temporary
SHOWS = [
    ('ming-smith', 'Ming Smith: Jazz Requiem – Notations in Blue', 'Exhibition', 'August 29, 2026 – January 17, 2027',
     'Whittemore Gallery', 'exhibition/ming-smith', '2026/06/EX_MS_29_Promo-scaled.jpg',
     'In the Whittemore and Noonan Galleries. Photographs by Ming Smith from the 1970s to now, shaped by dance, '
     'music and her years travelling in Europe; many printed large. Smith embodies a tenet of the Black Arts Movement: '
     '“owning the images that we saw of ourselves.” Curated by Daisy Desrosiers (The Gund at Kenyon College).', True),
    ('ming-smith-noonan', 'Ming Smith: Jazz Requiem (continued)', 'Exhibition', 'August 29, 2026 – January 17, 2027',
     'Noonan Gallery', 'exhibition/ming-smith',
     '2026/06/Ming-Smith-Installation-Photos_Mattatuck-Museum_Photo-Credit-Julie-Francois-10-scaled.jpg',
     'The show goes on in the Noonan Gallery, next door to the Whittemore Gallery.', True),
    ('franne-davids', 'Franne Davids and the World She Painted', 'Exhibition', 'October 10, 2026 – February 14, 2027',
     'Baker Gallery', 'exhibition/franne-davids', '2026/06/FD-24-scaled.jpg',
     'The first museum show of Franne Davids (1950–2022), born in Waterbury: living with schizophrenia, she painted more '
     'than 400 pictures in her parents’ basement, mostly of women she called her “girls”, her imaginary friends. '
     'Organized by Chief Curator Rebecca McNamara.', True),
    ('sonja-langford', 'Sonja Langford: Archives of Care', 'Exhibition', 'September 26, 2026 – January 3, 2027',
     'Munger Gallery', 'exhibition/sonja-langford-archives-of-care', '2026/07/Score-_7-Sonja-Langford.jpg',
     'The first-prize winner of the 2026 MIXMASTER competition looks into local archives and the history of American '
     'gynecology, healthcare and bodily autonomy, in photographs, books and installation.', True),
    ('highfield', 'Theodate Pope’s Highfield: A History', 'Exhibition', 'June 13 – December 13, 2026',
     'History Gallery', 'exhibition/theodate-popes-highfield-a-history',
     '2026/04/Highfield_MattScan_Image-via-Linda-Stevens_1_websize.jpg',
     'Highfield, the Middlebury estate that Theodate Pope Riddle, one of the first women architects in America, '
     'designed in 1911–14, seen in the Chamberlain family’s album photographs and Pope’s English Arts & Crafts '
     'designs.', True),
    ('our-community', 'Our Community', 'Exhibition', 'August 29 – November 8, 2026', 'Community Gallery',
     'exhibitions/community-gallery', '2026/09/Our-Community_REV-2.jpg',
     'Art and history from Waterbury-area schools and community groups, in the Monteiro Family Community Gallery '
     '(the show changes every few months).', True),
    ('collection', 'The Mattatuck Museum Collection', 'Gallery', 'Long-term', 'Upson Gallery',
     'collections/early-american-modern-galleries', '2026/02/Mattatuck-Collection-scaled.jpg',
     'American art from the 18th century to now, with a focus on Connecticut: Frederic Church, William Jennys, John '
     'Kensett, Charles Ethan Porter, John Vanderlyn and John Ferguson Weir; and in the 20th century Josef and Anni '
     'Albers, Alexander Calder, William Glackens, Jasper Johns, Sol LeWitt, Kiki Smith, Doug and Mike Starn, Kay Sage '
     'and Yves Tanguy.', False),
    ('buttons', 'The Waterbury Button Museum', 'Gallery', 'Long-term', 'Button Gallery',
     'collections/waterbury-button-museum', '2022/10/PXL_20221025_145524540-scaled.jpg',
     'More than 10,000 buttons from a collection of 20,000, made over 200 years in Waterbury, the “Brass City”, and '
     'around the world: carved cinnabar from Asia, Japanese netsuke, 1930s Bakelite, bouquets of human hair under '
     'glass, military buttons, Queen Victoria’s black glass, French “habitat” buttons with insects under glass, and '
     'four engraved buttons from George Washington’s coat. Assembled by Warren F. Kaynor for the Waterbury Button '
     'Company, given in 1999.', False),
    ('history', 'Waterbury: A City of Transitions', 'Gallery', 'Long-term', 'History Gallery',
     'collections/orton-p-camp-jr-history-exhibit', '2026/02/History-Gallery-lo-res.jpg',
     'The Orton P. Camp Jr. History Exhibit tells Waterbury’s turning points: English settlement and the displacement '
     'of Indigenous people, farm town to brass capital, the loss of the brass industry, and the city today.', False),
    ('fortune', 'Meet Fortune', 'Gallery', 'Long-term', 'History Gallery', 'collections/orton-p-camp-jr-history-exhibit',
     '2022/02/history.jpg',
     'The story of Fortune, an African American man enslaved in the Waterbury household of Dr. Preserved Porter in the '
     '18th century, of his family and of slavery in Waterbury; a kiosk shows the study of his skeleton.', False),
]

# ---- the collection (Connecticut Collections) --------------------------------------------------------------------------


def one(v):
    """'Oil, Oil' -> 'Oil'; 'Rosemary;Rosemary' -> 'Rosemary' (the catalogue repeats each value)."""
    v = re.sub(r'\s+', ' ', v or '').strip(' ,;')
    for sep in (';', ', '):
        parts = [p.strip() for p in v.split(sep)]
        if len(parts) % 2 == 0 and parts[:len(parts) // 2] == parts[len(parts) // 2:]:
            v = sep.join(parts[:len(parts) // 2])
    seen, out = set(), []
    for p in [p.strip() for p in v.split(', ')]:
        if p and p.lower() not in seen: seen.add(p.lower()); out.append(p)
    return ', '.join(out)


def unit(s, label):
    m = re.search(r'<!--\s*<label>' + label + r'</label>\s*-->(.*?)</div>', s, re.S)
    return m.group(1) if m else ''


def plain(s):
    s = re.sub(r'<br\s*/?>|</p>', '\n', s)
    t = html.unescape(re.sub(r'<[^>]+>', '', s))
    return re.sub(r'[ \t]+', ' ', '\n'.join(l.strip() for l in t.split('\n') if l.strip()))


def detail(oid):
    f = CACHE / 'detail' / f'{oid}.html'
    if not f.exists(): return {}
    s = f.read_text(encoding='utf-8', errors='ignore')
    d = {}
    m = re.search(r'<H1>(.*?)</H1>', s, re.S)
    if m: d['title'] = one(plain(m.group(1)))
    makers = re.findall(r'<a href="/index.php/Detail/entities/\d+">([^<]+)</a>\s*\(([^)]+)\)', s)
    who = [n.strip() for n, role in makers if re.search(r'creat|artist|maker|manufact|photograph|paint|design|'
                                                     r'engrav|print|publish|sculpt', role, re.I)]
    if who: d['artist'] = ', '.join(dict.fromkeys(who))
    m = re.search(r'<div class="unit">([^<]*?)\(Date [^)]*\)', s)
    if m: d['date'] = m.group(1).strip()
    d['medium'] = one(plain(unit(s, 'Medium')))
    d['material'] = one(plain(unit(s, 'Material')))
    desc = plain(unit(s, 'Description'))
    if desc: d['description'] = desc
    m = re.search(r"https://ctcollections\.org/media/[^'\"]+_large\.jpg", s)
    if m: d['image'] = m.group(0)
    return {k: v for k, v in d.items() if v}


def year(date):
    m = re.search(r'1[5-9]\d\d|20[0-2]\d', date or '')
    return int(m.group()) if m else None


def objtype(o, d):
    t = ' '.join([o['title'], d.get('medium', ''), d.get('material', '')]).lower()
    if 'button' in t: return 'Button'
    if o['kind'] == 'Still Image':
        if re.search(r'photograph|gelatin|albumen|daguerreo|tintype|ambrotype|cabinet card|carte', t): return 'Photograph'
        if re.search(r'oil|acrylic|tempera|painting|canvas|panel', t): return 'Painting'
        if re.search(r'watercolor|gouache|pastel|pencil|graphite|charcoal|ink|drawing|crayon', t): return 'Drawing'
        if re.search(r'print|lithograph|etching|engraving|woodcut|screen|bookplate', t): return 'Print'
        return 'Picture'
    return {'Physical Object': 'Object', 'Audio': 'Recording', 'Book': 'Book', 'Document': 'Document'}[o['kind']]


def place(typ):
    return {'Button': 'Button Gallery', 'Painting': 'Upson Gallery', 'Drawing': 'Upson Gallery',
            'Print': 'Upson Gallery', 'Picture': 'Upson Gallery', 'Photograph': 'History Gallery'}.get(typ,
                                                                                                  'History Gallery')


def build_works(floors):
    names = {r['id']: (r['name'], f['id']) for f in floors['floors'] for r in f['rooms']}
    works, rows = [], []
    for key, title, artist, date, room, path, photo, text, temp in SHOWS:
        page(path)
        name, fl = names[room]
        a = {'id': 'mm-' + key, 'title': title, 'artist': artist, 'date': date, 'type': artist,
             'description': text, 'url': f'{SITE}/{path}/', 'image': picture('mm-' + key, UP + photo),
             'imageCredit': 'Mattatuck Museum (mattmuseum.org)', 'gallery': room, 'galleryName': name, 'floor': fl,
             'placeGuessed': True, 'placeNote': 'Gallery named by the Mattatuck; where it is in the building is our '
                                                'reading (no plan is published).'}
        if temp: a['temporary'] = True
        works.append({k: v for k, v in a.items() if v not in (None, '')})
    objs = json.loads((CACHE / 'objects.json').read_text())
    highlights = 0
    for o in objs:
        d = detail(o['oid'])
        typ = objtype(o, d)
        room = place(typ)
        name, fl = names[room]
        title = d.get('title') or one(o['title']) or 'Untitled'
        medium = ', '.join(x for x in (d.get('medium'), d.get('material')) if x)
        row = {'id': 'mm-' + o['oid'], 'title': title, 'artist': d.get('artist') or ('Waterbury Button Company and '
               'others' if typ == 'Button' else 'Unknown maker'), 'date': d.get('date'), 'year': year(d.get('date')),
               'medium': medium or None, 'url': f'{CTC}/Detail/objects/{o["oid"]}',
               'imageUrl': d.get('image') or o.get('thumb'), 'onView': False, 'accession': o['acc'] or None}
        rows.append({k: v for k, v in row.items() if v not in (None, '')})
        # highlights on the map: art and objects the museum has written a label for (shown in a gallery before)
        label = d.get('description', '')
        if row.get('imageUrl') and len(label) > 250 and typ not in ('Recording', 'Document', 'Book'):
            highlights += 1
            a = {'id': row['id'], 'title': title, 'artist': row['artist'], 'date': row.get('date'),
                 'year': row.get('year'), 'type': typ, 'medium': medium or None,
                 'description': label + '\n\nIn the Mattatuck’s collection: it may be in storage today, ask whether '
                                        'it is on view.',
                 'url': row['url'], 'image': row['imageUrl'], 'accession': row.get('accession'),
                 'imageCredit': 'Mattatuck Museum, via Connecticut Collections', 'gallery': room,
                 'galleryName': name, 'floor': fl, 'placeGuessed': True,
                 'placeNote': 'In the collection; the gallery is our guess from what kind of object it is.'}
            works.append({k: v for k, v in a.items() if v not in (None, '')})
    for w in works:
        if w['id'].startswith('mm-') and not w['id'][3:].isdigit():
            rows.insert(0, {k: v for k, v in {'id': w['id'], 'title': w['title'], 'artist': w['artist'],
                            'date': w['date'], 'url': w['url'], 'imageUrl': w.get('image'), 'onView': True,
                            'gallery': w['gallery'], 'floor': w['floor']}.items() if v})
    by = {r['id']: r for r in rows}
    for w in works:                                          # highlights keep their gallery on the museum page
        if w['id'] in by and w['id'][3:].isdigit():
            by[w['id']].update(gallery=w['gallery'], floor=w['floor'])
    print(f'{len(works)} on the map ({highlights} collection highlights), {len(rows)} on the museum page, '
          f'{sum(1 for o in objs if (CACHE / "detail" / (o["oid"] + ".html")).exists())} object pages read')
    return works, rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    floors = build_floors()
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    works, rows = build_works(floors)
    checked = time.strftime('%Y-%m-%d')
    source = 'Mattatuck Museum (mattmuseum.org) and its catalogue on Connecticut Collections (ctcollections.org)'
    (OUT / 'artworks.json').write_text(json.dumps({'source': source, 'checked': checked, 'count': len(works),
                                                   'complete': False, 'artworks': works},
                                                  ensure_ascii=False, separators=(',', ':')))
    guide = {'museum': MUSEUM, 'name': NAME, 'checked': checked, 'source': source, 'onViewKnown': True,
             'note': 'The Mattatuck’s catalogue on Connecticut Collections lists 6,875 objects (art, Waterbury '
                     'history, brass, buttons, photographs), with pictures for most, but it doesn’t say what is on '
                     'view. Marked on view are the shows open now and the long-term galleries; the rest may be in '
                     'storage.',
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
