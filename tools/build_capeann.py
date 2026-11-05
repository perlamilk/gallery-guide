#!/usr/bin/env python3
"""Build the Cape Ann Museum (Gloucester, MA) map guide (run tools/harvest_capeann.py first, then this).

    data/capeann/floors.json       the Downtown Campus's four levels, seen from above (flat 2D)
    data/capeann/artworks.json     what is on view, placed in its gallery
    data/capeann/images/           pictures, made smaller for phones
    data/guides/Q15694003.json     the same list plus the rest, for the museum page

Where the information comes from
--------------------------------
Map: the museum's own "Map & Floor Guide" (capeannmuseum.org/wp-content/uploads/2026/06/CAM-Downtown-Map-and-Floor-
Guide.pdf, June 2026, linked as "Campus Map & Floor Guide" from the Downtown Campus page). It is a vector drawing of the
four levels stacked one above the other in an isometric view (walls at 30 and 150 degrees). Every floor outline and wall
below was read from the PDF's vector paths and turned back into a plan seen from straight above:
a page point (x, y) is the plan point (u, v) with x = cos30 (u + v) and y = sin30 (v - u) + the level's height on the
page (measured on the elevator shaft drawn through all four levels). The plan is shown with Pleasant Street (the
entrance) at the bottom; it is not turned north up. Room names, icons (restrooms, coat room, elevator, stairs, store,
reception, emergency exits) and the entrance were read from the drawing by eye. Facts from the Downtown Campus page:
one unisex restroom at the entrance, men's and women's restrooms (with changing tables) on Level 1, self-serve coat room
with free lockers, an elevator and lifts between levels, no café (coffee shops nearby), the Captain Elias Davis House
is not wheelchair accessible. Level 1A (Atrium Gallery and the Auditorium & Granite Gallery) is a few steps below
Level 1 and drawn with it.

Works: the museum has no online collection database yet. See tools/harvest_capeann.py for what is read: the museum's
own pictures and captions on capeannmuseum.org (media library, exhibition pages, news), and photos of works in the
galleries on Wikimedia Commons. The museum says where only a few things are (the Lane Gallery's Fitz Henry Lane
paintings, the Weems "Seated Cat" in the Sculpture Courtyard, the Fisheries Galleries); everything else is placed by
subject in the gallery that shows that subject, and says so.
"""
import html as H
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
from datetime import date
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'capeann'
CACHE = ROOT / '.cache' / 'capeann'
MUSEUM = 'Q15694003'
NAME = 'Cape Ann Museum'
UA = 'gallery-guide/1.0 (https://github.com/perlamilk/gallery-guide; personal museum guide)'
SITE = 'https://www.capeannmuseum.org/'
TODAY = date.today()


def P(u, v):
    """Plan point (PDF points, un-skewed) -> map units."""
    return [round((u - 40) * 3, 1), round((v - 30) * 3, 1)]


def rect(u0, v0, u1, v1):
    return [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]


# ---- Level 1 (Federal Street side; Level 1A a few steps down) -------------------------------------------------------
L1 = [
    ('Library & Archives', 'space', 'Library & Archives (research by appointment)',
     [(52.3, 67.0), (68.0, 51.3), (99.4, 49.7), (99.4, 117.3), (52.4, 117.2)], None),
    ('Archival Gallery', 'gallery', 'Archival Gallery', rect(52.4, 117.3, 99.3, 164.2), 'Archival'),
    ('Education Studio', 'space', 'Education Studio (classes and family programs)',
     [(115.4, 48.9), (146.1, 47.4), (145.9, 115.0), (111.6, 115.0), (111.7, 94.2), (115.4, 94.1)], None),
    ('Hall 1', 'corridor', 'Hall to the stairs, the restrooms and the galleries',
     [(99.4, 49.7), (115.4, 48.9), (115.4, 94.1), (111.7, 94.2), (111.6, 166.4), (117.3, 166.4), (117.3, 205.5),
      (99.3, 205.5)], None),
    ('Restrooms 1', 'space', 'Restrooms (men’s and women’s, accessible stalls, changing tables)',
     rect(111.6, 115.0, 136.5, 132.1), None),
    ('Restroom 1B', 'space', 'Restroom (accessible)', rect(111.6, 132.1, 126.1, 146.6), None),
    ('Stairs 1', 'corridor', 'Stairs and elevator lobby', rect(111.6, 146.6, 126.1, 166.4), None),
    ('Atrium Gallery 1A', 'gallery', 'Atrium Gallery (Level 1A, a few steps down)',
     [(136.4, 136.4), (149.5, 136.5), (148.2, 205.3), (117.3, 205.5), (117.3, 166.4), (126.2, 166.4), (126.1, 146.6)],
     'Atrium'),
    ('Auditorium & Granite Gallery', 'gallery', 'Auditorium & Granite Gallery (Level 1A): Cape Ann’s granite quarrying',
     [(53.2, 205.5), (148.2, 205.3), (147.0, 267.9), (53.1, 268.2)], 'Granite'),
    ('Museum Courtyard', 'space', 'Museum Courtyard (outdoors; the accessible way in from Federal Street)',
     rect(52.4, 164.2, 99.3, 205.5), None),
]
L1_CLOSED = []
L1_DOORS = [('Library & Archives', 'Hall 1', (99.4, 108)), ('Archival Gallery', 'Library & Archives', (91.7, 117.3)),
            ('Archival Gallery', 'Hall 1', (99.3, 154)), ('Education Studio', 'Hall 1', (113.5, 104)),
            ('Restrooms 1', 'Hall 1', (111.6, 129)), ('Restroom 1B', 'Hall 1', (111.6, 135)),
            ('Hall 1', 'Atrium Gallery 1A', (117.3, 176)), ('Hall 1', 'Stairs 1', (111.6, 156)),
            ('Stairs 1', 'Atrium Gallery 1A', (126.1, 156)), ('Atrium Gallery 1A', 'Auditorium & Granite Gallery', (132, 205.4)),
            ('Hall 1', 'Auditorium & Granite Gallery', (108, 205.5)), ('Hall 1', 'Museum Courtyard', (99.3, 186))]
L1_AMEN = [('stairs', 107, 58), ('restroom', 124, 123), ('restroom-all', 119, 139), ('elevator', 142, 141),
           ('stairs', 119, 156), ('emergency', 104, 52), ('entrance', 70, 196), ('emergency', 92, 186)]
L1_LABELS = [('Federal Street', 40, 170)]
L1_NOTES = [('Courtyard gate from Federal Street (accessible)', 58, 212)]

# ---- Level 2 (entrance from Pleasant Street) -------------------------------------------------------------------------
FHL = [(157.8, 210.7), (188.9, 210.7), (188.9, 185.3), (262.7, 185.3), (262.7, 211.0), (208.5, 211.5),
       (208.3, 234.6), (262.7, 234.0), (262.7, 269.5), (189.8, 269.3), (189.8, 243.7), (157.8, 243.7)]
L2 = [
    ('Elevator Lobby 2', 'corridor', 'Elevator and stairs', [(136.3, 136.2), (157.6, 138.8), (157.6, 157.6),
                                                            (134.6, 157.6), (136.3, 148.9)], None),
    ('Atrium Gallery 2', 'gallery', 'Atrium Gallery', rect(134.5, 157.6, 157.6, 196.4), 'Atrium'),
    ('Cape Ann Gallery', 'gallery', 'Cape Ann Gallery', [(63.7, 195.5), (128.7, 196.4), (128.7, 257.8), (63.9, 257.9)],
     'Cape Ann'),
    ('Central Gallery', 'gallery', 'Central Gallery (tours start here)', [(128.7, 196.4), (157.6, 196.4),
                                                                         (157.7, 257.7), (128.6, 257.8)], 'Central'),
    ('Fitz Henry Lane Gallery', 'gallery', 'Fitz Henry Lane Gallery', FHL, 'Fitz Henry Lane'),
    ('Spotlight Gallery', 'gallery', 'Spotlight Gallery', [(208.5, 211.5), (262.7, 211.0), (262.7, 234.0),
                                                          (208.3, 234.6)], 'Spotlight'),
    ('Coat Hall', 'corridor', 'Hall to the coat room and restroom', rect(157.8, 243.7, 189.8, 254.7), None),
    ('Coat Room', 'space', 'Coat Room (self-serve, free lockers)', rect(159.5, 254.7, 178.7, 269.4), None),
    ('Restroom 2', 'space', 'Restroom (unisex, accessible)', rect(178.7, 254.7, 189.8, 269.4), None),
    ('Steps', 'corridor', 'Steps between the galleries and Reception', rect(128.6, 257.8, 152.2, 272.2), None),
    ('Ramp', 'corridor', 'Ramp and lift up to the galleries', [(152.2, 257.8), (157.8, 257.7), (157.8, 254.7),
                                                               (159.5, 254.7), (159.5, 269.4), (157.8, 306.6),
                                                               (151.1, 297.9)], None),
    ('Reception', 'space', 'Reception and Visitor Services desk (tickets, Lost & Found)',
     [(129.0, 272.2), (152.2, 272.2), (151.1, 297.9), (157.8, 306.6), (128.6, 305.5), (128.9, 295.0)], None),
    ('Museum Store', 'space', 'Museum Store', [(71.8, 257.9), (128.6, 257.8), (128.6, 272.2), (129.0, 272.2),
                                              (128.9, 295.0), (117.3, 294.2), (70.4, 292.1)], None),
    ('Capt. Elias Davis House', 'gallery', 'Captain Elias Davis House (1804, period rooms; not wheelchair accessible)',
     [(70.4, 292.1), (128.9, 295.0), (128.6, 305.5), (126.9, 344.4), (68.3, 344.5)], 'Davis House'),
    ('Sculpture Courtyard', 'space', 'Sculpture Courtyard (outdoors)', [(159.5, 269.4), (262.7, 269.3), (261.1, 340.1),
                                                                         (155.8, 340.0), (157.7, 306.5)], None),
]
L2_DOORS = [('Elevator Lobby 2', 'Atrium Gallery 2', (146, 157.6)), ('Atrium Gallery 2', 'Central Gallery', (143.5, 196.4)),
            ('Cape Ann Gallery', 'Central Gallery', (128.7, 225)), ('Central Gallery', 'Fitz Henry Lane Gallery', (157.7, 225)),
            ('Fitz Henry Lane Gallery', 'Spotlight Gallery', (220, 234.5)), ('Central Gallery', 'Steps', (141, 257.8)),
            ('Steps', 'Reception', (141, 272.2)), ('Steps', 'Ramp', (152.2, 262)), ('Ramp', 'Coat Hall', (158.6, 254.7)),
            ('Coat Hall', 'Coat Room', (166, 254.7)), ('Coat Hall', 'Restroom 2', (184, 254.7)),
            ('Ramp', 'Reception', (151.6, 285)), ('Reception', 'Museum Store', (129, 283)),
            ('Reception', 'Capt. Elias Davis House', (128.8, 300)), ('Fitz Henry Lane Gallery', 'Sculpture Courtyard', (200, 269.4)),
            ('Ramp', 'Sculpture Courtyard', (158.5, 290))]
L2_AMEN = [('elevator', 150, 143), ('stairs', 140, 152), ('coat', 168, 262), ('restroom-all', 184, 262),
           ('info', 140, 288), ('shop', 100, 275), ('entrance', 143, 302), ('emergency', 176, 212),
           ('emergency', 259, 255), ('stairs', 143, 265)]
L2_LABELS = [('Pleasant Street', 150, 362)]
L2_NOTES = [('Entrance & exit (ramp, automatic door)', 143, 350)]

# ---- Level 3 -----------------------------------------------------------------------------------------------------------
L3 = [
    ('Fisheries Gallery II', 'gallery', 'Fisheries Gallery II', [(62.8, 56.6), (78.3, 41.1), (109.8, 39.5),
                                                                 (109.8, 153.8), (62.8, 153.7)], 'Fisheries II'),
    ('Fisheries Gallery III', 'gallery', 'Fisheries Gallery III', rect(109.8, 39.2, 123.2, 131.2), 'III'),
    ('Fisheries Gallery I', 'gallery', 'Fisheries Gallery I', [(123.2, 38.8), (156.5, 37.0), (156.6, 109.0),
                                                               (123.2, 109.0)], 'Fisheries I'),
    ('Fisheries Gallery IV', 'gallery', 'Fisheries Gallery IV', [(123.2, 109.0), (156.6, 109.0), (156.6, 116.1),
                                                                 (136.3, 136.3), (123.2, 136.2)], 'Fisheries IV'),
    ('Elevator Lobby 3', 'corridor', 'Elevator and stairs', [(109.8, 131.2), (123.2, 131.2), (123.2, 136.2), (136.3, 136.3),
                                                            (135.9, 148.9), (124.3, 148.7), (124.4, 154.6), (120.6, 154.6),
                                                            (120.6, 164.2), (109.7, 164.2)], None),
]
L3_DOORS = [('Fisheries Gallery II', 'Fisheries Gallery III', (109.8, 76)), ('Fisheries Gallery III', 'Fisheries Gallery I', (123.2, 73)),
            ('Fisheries Gallery III', 'Fisheries Gallery IV', (123.2, 120)), ('Fisheries Gallery II', 'Fisheries Gallery III', (109.8, 120)),
            ('Fisheries Gallery III', 'Elevator Lobby 3', (116, 131.2)), ('Fisheries Gallery IV', 'Elevator Lobby 3', (128, 136.2)),
            ('Fisheries Gallery I', 'Fisheries Gallery IV', (140, 109))]
L3_AMEN = [('stairs', 101, 61), ('elevator', 130, 142), ('stairs', 115, 152)]

# ---- Level 4 -----------------------------------------------------------------------------------------------------------
L4 = [
    ('Atrium Gallery 4', 'gallery', 'Atrium Gallery', [(136.2, 136.1), (156.7, 139.5), (157.1, 192.8), (134.3, 192.4),
                                                      (134.5, 183.4), (137.7, 175.6), (140.6, 169.5), (141.1, 161.9),
                                                      (141.4, 154.7), (147.3, 148.8), (136.1, 149.0)], 'Atrium'),
    ('20th & 21st Centuries Gallery', 'gallery', '20th & 21st Centuries Gallery',
     rect(63.9, 192.7, 127.2, 258.3), '20th & 21st Centuries'),
    ('Special Exhibits Gallery I', 'gallery', 'Special Exhibits Gallery I', rect(127.2, 192.8, 157.1, 258.4), 'Special I'),
    ('Special Exhibits Gallery III', 'gallery', 'Special Exhibits Gallery III', rect(157.1, 210.5, 188.0, 244.3), 'III'),
    ('Special Exhibits Gallery II', 'gallery', 'Special Exhibits Gallery II', rect(157.0, 244.3, 188.1, 269.3), 'II'),
    ('Special Exhibits Gallery IV', 'gallery', 'Special Exhibits Gallery IV',
     [(188.0, 186.2), (262.6, 186.0), (262.6, 202.3), (256.3, 202.3), (256.4, 254.7), (262.5, 254.9), (262.6, 269.2),
      (188.1, 269.3)], 'Special IV'),
    ('Landing 4', 'corridor', 'Stairs and lift down to the Folly Cove Designers Gallery',
     [(127.3, 258.3), (156.9, 258.4), (156.9, 269.4), (151.3, 275.0), (132.6, 275.1), (132.7, 266.9), (121.5, 266.9),
      (127.1, 261.3)], None),
    ('Folly Cove Designers Gallery', 'gallery', 'Folly Cove Designers Gallery (a few steps down; lift)',
     [(121.5, 266.9), (132.7, 266.9), (132.6, 275.1), (151.3, 275.0), (149.8, 311.6), (120.3, 310.1)], 'Folly Cove'),
]
L4_DOORS = [('Atrium Gallery 4', 'Special Exhibits Gallery I', (143, 192.8)),
            ('20th & 21st Centuries Gallery', 'Special Exhibits Gallery I', (127.2, 227)),
            ('Special Exhibits Gallery I', 'Special Exhibits Gallery III', (157.1, 227)),
            ('Special Exhibits Gallery III', 'Special Exhibits Gallery II', (174.5, 244.3)),
            ('Special Exhibits Gallery III', 'Special Exhibits Gallery IV', (188.0, 227)),
            ('Special Exhibits Gallery I', 'Landing 4', (142, 258.4)), ('Landing 4', 'Folly Cove Designers Gallery', (141, 275.0))]
L4_AMEN = [('elevator', 150, 143), ('stairs', 140, 144), ('stairs', 139, 268), ('elevator', 152, 265),
           ('emergency', 176, 212), ('emergency', 253, 208), ('emergency', 124, 280)]


def inside(p, pg):
    x, y = p
    c = False
    for i in range(len(pg)):
        (x1, y1), (x2, y2) = pg[i], pg[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c


def floor(fid, label, order, area_text, spec, doors, amen, labels=(), notes=()):
    rooms = []
    for rid, kind, name, pg, short in spec:
        r = {'id': rid, 'kind': kind, 'name': name, 'poly': [P(*q) for q in pg]}
        if short: r['label'] = short
        rooms.append(r)
    ids = [r['id'] for r in rooms]
    assert len(ids) == len(set(ids)), fid
    for a, b, at in doors:
        assert a in ids and b in ids, (fid, a, b)
    fl = {'id': fid, 'label': label, 'order': order, 'transform': [1, 0, 0], 'area': area_text, 'rooms': rooms,
          'closed': [], 'amenities': [{'type': t, 'at': P(x, y)} for t, x, y in amen],
          'labels': [{'text': t, 'kind': 'area', 'at': P(x, y)} for t, x, y in labels],
          'notes': [{'text': t, 'kind': 'note', 'at': P(x, y)} for t, x, y in notes],
          'doors': [{'a': a, 'b': b, 'at': P(*at), 'width': 14, 'axis': 'o'} for a, b, at in doors]}
    for a in fl['amenities']:
        assert any(inside(a['at'], r['poly']) for r in rooms), (fid, a)
    return fl


def build_floors():
    floors = [
        floor('1', 'Level 1 & 1A', 0, 'Library & Archives, Archival Gallery, Education Studio, restrooms, Museum '
              'Courtyard; a few steps down (1A): Atrium Gallery and the Auditorium & Granite Gallery',
              L1, L1_DOORS, L1_AMEN, L1_LABELS, L1_NOTES),
        floor('2', 'Level 2 (entrance)', 1, 'Reception, Museum Store, Davis House, Fitz Henry Lane, Cape Ann, Central, '
              'Atrium and Spotlight Galleries, Sculpture Courtyard',
              L2, L2_DOORS, L2_AMEN, L2_LABELS, L2_NOTES),
        floor('3', 'Level 3', 2, 'Fisheries Galleries I–IV', L3, L3_DOORS, L3_AMEN),
        floor('4', 'Level 4', 3, '20th & 21st Centuries Gallery, Atrium Gallery, Folly Cove Designers Gallery, '
              'Special Exhibits Galleries I–IV', L4, L4_DOORS, L4_AMEN),
    ]
    # the Fitz Henry Lane Gallery wraps around the Spotlight Gallery: put its name in the wide part
    for r in floors[1]['rooms']:
        if r['id'] == 'Fitz Henry Lane Gallery': r['labelAt'] = P(176, 227)
    return {'about': 'Built by tools/build_capeann.py from the Cape Ann Museum’s own Map & Floor Guide (June 2026), '
                     'whose isometric drawing was turned back into flat plans. Pleasant Street (the entrance) is at the '
                     'bottom; the map is not north up. You come in on Level 2; Level 3 (Fisheries) and Level 4 are '
                     'upstairs, Level 1 and the Granite Gallery (1A) downstairs. Room shapes follow the drawing’s walls; '
                     'icons are placed by eye.',
            'source': 'Cape Ann Museum: Map & Floor Guide (June 2026) and the Downtown Campus visit page',
            'units': 'PDF points of the un-skewed drawing x 3', 'approximate': False, 'defaultFloor': '2',
            'galleryWord': 'Gallery', 'floors': floors}


# ---- pictures ------------------------------------------------------------------------------------------------------

def fetch(url, dest, pause=4):
    if dest.exists() and dest.stat().st_size > 2000: return True
    if os.environ.get('NO_DOWNLOAD'): return False       # build from what is already cached
    dest.parent.mkdir(parents=True, exist_ok=True)
    for wait in (0, 60, 180, 420):
        time.sleep(wait or pause)
        r = subprocess.run(['curl', '-s', '-L', '-m', '90', '-A', UA, '-w', '%{http_code}', '-o', str(dest), url],
                           capture_output=True, text=True)
        if r.stdout.strip() == '200' and dest.exists() and dest.stat().st_size > 2000: return True
        dest.unlink(missing_ok=True)
        if r.stdout.strip() not in ('429', '000', '503', '502'): break
    return False


def picture(key, url, size=1000):
    if not url: return None
    dest = OUT / 'images' / f'{key}.jpg'
    rel = f'data/capeann/images/{key}.jpg'
    if dest.exists(): return rel
    raw = CACHE / 'img' / (key + '.bin')
    if not fetch(url, raw):
        print(f'  no picture: {url}')
        return None
    try:
        im = Image.open(io.BytesIO(raw.read_bytes()))
        im.load()
    except Exception as e:
        print(f'  bad picture {url}: {e}')
        return None
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA')
        bg = Image.new('RGB', im.size, 'white')
        bg.paste(im, mask=im.split()[-1])
        im = bg
    im = im.convert('RGB')
    im.thumbnail((size, size))
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, 'JPEG', quality=78, optimize=True, progressive=True)
    return rel


def slug(s):
    return re.sub(r'[^0-9a-z]+', '-', s.lower()).strip('-')[:60]


def text(s):
    return H.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s or ''))).strip()


# ---- where things go -------------------------------------------------------------------------------------------------
LANE = 'Fitz Henry Lane Gallery'
GUESS = ('Placed by subject: the museum doesn’t publish where each object hangs since the galleries were renovated '
         '(reopened June 2026), so it may be elsewhere or in storage. Ask at Reception.')
OLD_PHOTO = ('Photo taken in the galleries before the 2025–26 renovation; placed by subject in the gallery that shows '
             'it now, so it may be elsewhere or in storage. Ask at Reception.')


def subject_room(title, artist, when, medium, category=''):
    """-> the gallery that shows this kind of thing (the museum's own floor guide names the galleries by subject)."""
    t = ' '.join(x or '' for x in (title, artist, medium, category)).lower()
    year = int(m.group(0)) if (m := re.search(r'1[5-9]\d\d|20[0-2]\d', when or '')) else None
    if 'lane' in (artist or '').lower() and 'fitz' in (artist or '').lower() or 'mellen' in t: return LANE
    if re.search(r'folly cove|virginia lee burton|demetrios.*block|hand-blocked|linoleum', t): return 'Folly Cove Designers Gallery'
    if re.search(r'granite|quarr|paving|derrick', t): return 'Auditorium & Granite Gallery'
    if re.search(r'schooner|fisherm|fishing|fisher|dory|trawl|vessel|ship model|model by|lighthouse|fresnel|lens|'
                 r'navigat|compass|sextant|radio|billet head|figurehead|harpoon|whal|nets?\b|lobster|cod|halibut|'
                 r'tobacco tin|float lamp|sail', t):
        if re.search(r'lighthouse|fresnel|lens|float lamp', t): return 'Fisheries Gallery IV'
        if re.search(r'model|schooner|vessel|billet head|figurehead', t): return 'Fisheries Gallery II'
        if re.search(r'radio|navigat|compass|sextant|tobacco', t): return 'Fisheries Gallery III'
        return 'Fisheries Gallery I'
    if re.search(r'furniture|chair|table|desk|chest|clock|silver|tankard|teapot|porringer|ceramic|porcelain|'
                 r'earthenware|stoneware|creamware|sampler|globe', t): return 'Capt. Elias Davis House'
    if re.search(r'sculpture|bronze|marble|plaster|carved', t) and (year or 0) >= 1900: return 'Atrium Gallery 2'
    if year and year >= 1900: return '20th & 21st Centuries Gallery'
    return 'Cape Ann Gallery'


# ---- shows and things the museum places itself ------------------------------------------------------------------------
# (key, gallery, title, maker, (from, to), exhibition slug, media id for the picture, gallery known?)
SHOWS = [
    ('rearick', 'Special Exhibits Gallery IV', 'This Other Eden: Photographs by Anne Rearick', 'Anne Rearick',
     ('2026-11-14', '2027-03-21'), 'this-other-eden-anne-rearick', 18903, False),
    ('archives', 'Archival Gallery', '150 Years and Beyond: Highlights from the Library & Archives',
     'Cape Ann Museum Library & Archives', ('2026-11-14', '2027-04-25'),
     '150-years-and-beyond-highlights-from-the-library-and-archives', 18971, False),
]
SHOW_GUESS = ('The museum doesn’t say which gallery this show is in, so its place on the map is a guess. Ask at '
              'Reception.')
# things the museum's own news says where they are: (gallery, title, artist, date, medium, text, media id)
PLACED = [
    ('Sculpture Courtyard', 'Seated Cat (Sphinx)', 'Katharine Lane Weems', '1941 (enlarged 2026)', 'Bronze',
     'An eight-foot bronze enlargement of Weems’s 18-inch cat of 1941, made by Robert Shure of Skylight Studios and '
     'set in the granite courtyard in May 2026.', None),
    (LANE, 'Untitled (Floral Still Life)', 'Fitz Henry Lane', '1849', 'Oil on board',
     'A rare still life by the maritime painter: flowers picked on Middle Street, painted and given to a friend. '
     'A gift that came home in 2025; cleaning brought back its colors.', 15205),
    (LANE, 'Shooting Seabirds', 'Fitz Henry Lane', '1842', 'Graphite and watercolor on paper',
     'An early work from Lane’s move from printmaking to painting; a gift of Jane Wyeth.', None),
]


def fmt(d):
    d = date.fromisoformat(d)
    return f'{d:%b} {d.day}, {d.year}'


def media_by_id():
    return {m['id']: m for m in json.load(open(CACHE / 'media.json'))}


def show_text(slug):
    for e in json.load(open(CACHE / 'exhibitions.json')):
        if e['slug'] == slug:
            t = text(e['content']['rendered'])
            m = re.search(r'Overview (.*?)(?: Read the Press Release| Image [Cc]redit| Related Programs|$)', t)
            if not m: m = re.search(r'Exhibition Details (?:Previous |Next )*(.*?)(?: Image [Cc]redit| Related Programs|$)', t)
            return (m.group(1) if m else t)[:700].strip()
    return None


# ---- the museum's own captioned pictures (media library) --------------------------------------------------------------
# Works of the museum's collection that capeannmuseum.org shows with a caption (copied from the caption; loans left out):
# (media id, title, artist, date, medium, credit line, accession, gallery or None for "by subject")
MEDIA = [
    (18736, 'Swordfisherman', 'Gifford Beal', '1930s', 'Oil on board', 'Museum purchase, 2025', '2025.061.001', None),
    (18717, 'Scavenger Rocks', 'John Sloan', '1914', 'Oil on canvas',
     'Gift of Stephen Lindo in memory of Sigrid Elizabeth Olson, 2024', '2024.043.002', None),
    (14632, 'Gloucester Inlet', 'John Sloan', '1914', 'Oil on canvas', 'Gift of the Dr. Joseph E. Geary Family, 2023',
     '2023.061.001', None),
    (16608, 'Summer Outward Bound, Gloucester', 'Marsden Hartley', '1931', 'Oil on board',
     'Gift of the estate of Robert L. French, 2009', '2009.51.9', None),
    (6912, 'New England Ladies', 'Theresa Bernstein', '1925', 'Oil on canvas', None, '2510.03', None),
    (16941, 'Self-Portrait', 'Alice Beach Winter', 'early 20th century', 'Oil on canvas', 'Gift of Elsa Marshall', None,
     '20th & 21st Centuries Gallery'),
    (16953, 'Self-Portrait of the Artist', 'Vincent Castagnacci', '1964', 'Oil on canvas', 'Gift of the artist, 2022',
     '2022.047.001', None),
    (16942, 'Neon Electrician (Self-Portrait)', 'Jon Sarkin', '2011', 'Mixed media on canvas',
     'Museum purchase, 2025, with support from Kermit and Glenys Birchfield and an anonymous donor', '2025.038.001', None),
    (16226, 'Good Harbor Beach Scene', 'Joseph Solman', '1980', 'Monotype on paper', 'Estate of Robert L. French, 2009',
     '2009.051.010', None),
    (8951, 'Niles Beach', 'Elaine Wing', '1995', 'Oil on canvas', 'Gift of Elizabeth and Robert L. French, 2009',
     '2009.51.19', None),
    (18329, 'In Her Garden', 'Erma Wheeler', 'c. 1980', 'Watercolor on paper',
     'Gift of the Stella and Charles Guttman Foundation, 2024', '2024.040.001', None),
    (18315, 'Essex Farm', 'Zygmund Jankowski', 'c. 1999', 'Oil on canvas', 'Gift of Myra Hall, 2026', None, None),
    (18639, 'Reina at 13', 'Anne Rearick', '2025', 'Archival print',
     'Museum purchase with funds provided by the Kanter Kallman Foundation, 2025', '2025.064.001',
     'Special Exhibits Gallery IV'),
    (15648, 'Etruscan King and Consort', 'Aristides Demetrios', '2021', 'Stainless steel',
     'Gift of Aristides Burton Demetrios and Ilene H. Nagel (Demetrios), 2021', '2021.045', 'Sculpture Courtyard'),
    (14768, 'Fisherman', 'Augustus W. Buhler', 'c. 1895', 'Oil on canvas',
     'Gift of Dorothy Buhler, the artist’s daughter, 1980', '2202.3', None),
    (7903, 'Shoving Off', 'Augustus W. Buhler', '1907', 'Oil on canvas', 'Gift of Dr. Bernard Cohen, 1979', '2199', None),
    (14648, 'The Derrick', 'Gabrielle de Veaux Clements', '1884', 'Etching on paper', 'Gift of Harold and Betty Bell, 1999',
     '1999.037.01', None),
    (8607, 'A Colonial Apple Gathering (mural)', 'Gabrielle de Veaux Clements', 'c. 1892', 'Oil on canvas',
     'Gift of the estate of Walker Hancock, 2001', '2001.27.15', None),
    (15754, 'View of the Babson and Ellery Houses, Gloucester', 'Fitz Henry Lane', '1863', 'Oil on canvas',
     'Gift of Roger W. Babson, 1937', '779.02', None),
    (2299, 'Three Master on the Gloucester Railway', 'Fitz Henry Lane', '1857', 'Oil on canvas', None, None, None),
]


# ---- Wikimedia Commons (photos taken in the galleries; file names carry the label) --------------------------------------
def commons_url(name, width=960):
    import hashlib
    f = name.replace(' ', '_')
    h = hashlib.md5(f.encode()).hexdigest()
    q = urllib.parse.quote(f)
    return f'https://upload.wikimedia.org/wikipedia/commons/thumb/{h[0]}/{h[:2]}/{q}/{width}px-{q}'


def parse_commons(fname):
    """'Title, by Artist, 1850, oil on canvas - Cape Ann Museum - Gloucester, MA - DSC01153.jpg' -> parts."""
    base = re.sub(r'^File:', '', fname)
    m = re.match(r'(.+?) - Cape Ann Museum - Gloucester, MA - DSC\d+(?: \(\d\))?\.(?:jpe?g|JPG)$', base)
    if not m: return None
    label = m.group(1)
    if label.lower().startswith(('cape ann museum', 'gallery', 'interior', 'exterior')): return None
    artist = None
    by = (re.search(r',? with artwork by ([^,]+)', label)
          or re.search(r', (?:painted |carved |drawn |made |model |modeled |designed |engraved |printed )?by ([^,]+)', label))
    if by:
        artist = re.sub(r' in correspondence with .*', '', by.group(1).strip())
        label = label[:by.start()] + label[by.end():]
    parts = [p.strip() for p in label.split(',')]
    di = next((i for i, p in enumerate(parts) if i and re.search(r'\b1[5-9]\d\d|\b20[0-2]\d|undated|century', p)), None)
    if di is None:
        title, when, medium = ', '.join(parts[:1]), None, ', '.join(parts[1:]) or None
    else:
        title, when, medium = ', '.join(parts[:di]), parts[di], ', '.join(parts[di + 1:]) or None
    if title.lower().endswith(' detail') or ', detail' in label: return None
    if not artist and (m := re.match(r'(.+?) by ([A-Z][^,]+)$', title)):
        title, artist = m.group(1), m.group(2)
    if medium:
        if re.search(r'\bview [2-9]\b', medium): return None          # one photo of each object is enough
        medium = re.sub(r',? ?view 1\b', '', medium).strip(' ,') or None
    return title, artist, when, (medium[0].upper() + medium[1:]) if medium else None


def build_works(floors):
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    media = media_by_id()
    works, extra, seen = [], [], set()

    def add(a, room, note):
        key = re.sub(r'[^a-z0-9]', '', (a['title'] + (a.get('artist') or '')).lower())
        if key in seen: return
        seen.add(key)
        if room:
            fl, gname = rooms[room]
            a.update(gallery=room, galleryName=gname, floor=fl, placeNote=note)
            works.append({k: v for k, v in a.items() if v not in (None, '', [])})
        else:
            extra.append({k: v for k, v in a.items() if v not in (None, '', [])})

    for key, room, title, maker, (d0, d1), slug_, mid, known in SHOWS:
        if date.fromisoformat(d1) < TODAY: continue
        desc = show_text(slug_)
        if date.fromisoformat(d0) > TODAY: desc = f'Opens {fmt(d0)}. ' + (desc or '')
        img = picture(f'capeann-show-{key}', media.get(mid, {}).get('source_url'))
        add({'id': f'capeann-show-{key}', 'title': title, 'artist': maker, 'date': f'{fmt(d0)} – {fmt(d1)}',
             'medium': 'Exhibition', 'description': desc, 'url': SITE + f'exhibition/{slug_}/', 'image': img,
             'imageCredit': 'Cape Ann Museum' if img else None, 'temporary': True}, room, None if known else SHOW_GUESS)

    for i, (room, title, artist, when, medium, desc, mid) in enumerate(PLACED):
        img = picture(f'capeann-placed-{slug(title)}', media.get(mid, {}).get('source_url')) if mid else None
        add({'id': f'capeann-placed-{i}', 'title': title, 'artist': artist, 'date': when, 'medium': medium,
             'description': desc, 'url': SITE + 'about/news/', 'image': img,
             'imageCredit': 'Cape Ann Museum' if img else None}, room, None)

    for mid, title, artist, when, medium, credit, acc, room in MEDIA:
        room = room or subject_room(title, artist, when, medium)
        img = picture(f'capeann-{slug(artist + "-" + title)}', media.get(mid, {}).get('source_url'))
        desc = '. '.join(x for x in (credit, f'Accession {acc}' if acc else None) if x)
        add({'id': f'capeann-m-{mid}', 'title': title, 'artist': artist, 'date': when, 'medium': medium,
             'description': (desc + '.') if desc else None, 'accession': acc, 'url': SITE + 'all-collections/',
             'image': img, 'imageCredit': 'Cape Ann Museum' if img else None}, room, GUESS if room != LANE else None)

    files = json.load(open(CACHE / 'commons.json')) if (CACHE / 'commons.json').exists() else {}
    for fname, cat in sorted(files.items()):
        p = parse_commons(fname)
        if not p: continue
        title, artist, when, medium = p
        room = subject_room(title, artist, when, medium, cat)
        name = re.sub(r'^File:', '', fname)
        img = picture(f'capeann-c-{re.search(r"DSC(\d+)", name).group(1)}', commons_url(name))
        add({'id': f'capeann-c-{re.search(r"DSC(\d+)", name).group(1)}', 'title': title, 'artist': artist, 'date': when,
             'medium': medium, 'url': 'https://commons.wikimedia.org/wiki/' + urllib.parse.quote(fname.replace(' ', '_')),
             'image': img, 'imageCredit': 'Photo: Daderot, Wikimedia Commons (public domain)' if img else None},
            room, OLD_PHOTO if room != LANE else 'Photo taken before the 2025–26 renovation; the museum’s Lane '
                                                 'paintings and prints hang in this gallery.')

    return ({'source': 'Cape Ann Museum: capeannmuseum.org (exhibitions, news, captioned pictures); Wikimedia Commons '
                       'photos of the galleries (Daderot)',
             'checked': TODAY.isoformat(), 'count': len(works), 'complete': False, 'artworks': works}, extra)


def build_guide(works, extra):
    rows = []
    for a, on in [(a, True) for a in works['artworks']] + [(a, False) for a in extra]:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a.get('artist'),
                     'date': a.get('date'), 'medium': a.get('medium'), 'url': a['url'], 'imageUrl': a.get('image'),
                     'onView': on, 'gallery': a.get('gallery'), 'floor': a.get('floor')}.items()
                     if v not in (None, '')})
    return {'museum': MUSEUM, 'name': NAME, 'checked': TODAY.isoformat(),
            'source': 'capeannmuseum.org and Wikimedia Commons (Daderot’s photos of the galleries)',
            'onViewKnown': False,
            'note': 'The museum has no online collection yet. These are the works it shows and captions on its website, '
                    'its current shows, and objects photographed in its galleries, placed in the gallery for their '
                    'subject. The Fitz Henry Lane Gallery holds the world’s largest Lane collection.',
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
    from collections import Counter
    print(f'{works["count"]} on the map ({sum("image" in a for a in works["artworks"])} with pictures), '
          f'{len(extra)} more in the list')
    print(Counter(a['gallery'] for a in works['artworks']))


if __name__ == '__main__':
    sys.exit(main())
