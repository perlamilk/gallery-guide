#!/usr/bin/env python3
"""Build the New Bedford Whaling Museum map guide (run: python3 tools/harvest_nbwm.py, then this).

    data/nbwm/floors.json       Lobby & Lower Level, Main Level and Upper Level, seen from above (flat 2D)
    data/nbwm/artworks.json     galleries, the whale skeletons, the Lagoda and objects, in the room where they are
    data/nbwm/images/           pictures from whalingmuseum.org, made smaller for phones
    data/guides/Q7005471.json   the same, for the museum page

Where the information comes from
--------------------------------
The map is traced from the museum's own map of its three levels, printed in its 2026 self-guide
("General-Self-Guide-2026.pdf") and its Visitors Guide (NBWM_VisGuide24_v5.pdf, which adds the key: restrooms,
all-gender restroom, information, the two kinds of elevator, stairs, emergency exits, ramps). The self-guide holds
the three plans as three pictures (Main Level 1713 x 694 px, Lobby & Lower Level 706 x 558 px, Upper Level
1258 x 534 px). Coordinates here are Main Level picture pixels (times 2). The other two plans are scaled onto it:
the Upper Level x 1/0.76 so the Lagoda balcony lies over the Lagoda gallery and the two Main-to-Upper elevators line
up (both match to a pixel); the Lower Level x 1.5 so its elevator and spiral stair sit under the Main Level's.
Rooms and amenities are where the museum's map puts them; walls are simplified to straight lines.

Captain Paul Cuffe Park is outdoors; the Visitors Guide draws it beside the Lower Level plan, so where it is drawn
here is approximate.

The works: the museum's WordPress pages (tools/harvest_nbwm.py): the Permanent Exhibitions page, every exhibition
on view now (their pictures carry captions with the object's maker, date and accession number), the four whale
skeleton pages and the plastic scrimshaw page. Gallery names in the posts (Wattles Family Gallery, Scrimshaw Gallery
Annex, Braitmayer Family Galleries) are matched to the map's "Rotating Exhibition" rooms; where that match is our
guess the work says so.
"""
import html
import io
import json
import re
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'nbwm'
CACHE = ROOT / '.cache' / 'nbwm'
MUSEUM = 'Q7005471'
NAME = 'New Bedford Whaling Museum'
SITE = 'https://www.whalingmuseum.org'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
GUESS = '(approximate)'


def P(x, y):
    return [round(x * 2, 1), round(y * 2, 1)]


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# Each level's own picture pixels -> Main Level picture pixels
MOVE = {
    'L': lambda x, y: ((x - 437) * 1.5 + 583, (y - 292) * 1.5 + 373),
    'ML': lambda x, y: (x, y),
    'UL': lambda x, y: ((x - 555) / 0.76 + 750, (y - 343) / 0.76 + 445),
}

# ---- Lobby & Lower Level (pixels of the self-guide's Lower Level picture) -------------------------------------
# rooms: (id, kind, name, polygon, short label for galleries)

LOWER = [
    ('Theater', 'gallery', 'Theater: the 3D movie about the natural world, on the half hour from 10:30 to 2:30 (extra ticket)',
     [(104, 177), (170, 115), (285, 115), (285, 268), (222, 307), (104, 307)], 'Theater'),
    ('Whales Today', 'gallery', 'Whales Today (Jacobs Family Gallery): the whale skeletons overhead, the life-size blue '
     'whale heart, the sand table and the science of living whales',
     [(288, 115), (422, 115), (422, 277), (390, 277), (390, 310), (345, 308), (318, 295), (305, 270), (288, 250)],
     'Whales Today'),
    ('Local Artist Showcase', 'gallery', 'Local Artist Showcase (free, no ticket needed)', rect(390, 277, 422, 310),
     'Local Artists'),
    ('Old Dartmouth Historical Society', 'gallery', 'The Old Dartmouth Historical Society (Dr. Gilbert and Frima Shapiro '
     'Gallery): the museum’s history, local art glass, silver, furniture and paintings', rect(425, 115, 497, 275),
     'Old Dartmouth'),
    ('Wattles Family Gallery', 'gallery', 'Wattles Family Gallery: special exhibitions',
     [(500, 115), (600, 115), (600, 340), (550, 340), (550, 305), (500, 305)], 'Wattles'),
    ('Lobby', 'space', 'Lobby: Admission Desk, information, coat room with free lockers, elevator to the Main Level. '
     'You may eat your own food here. Highlights Tours leave from here at 11 am and 2 pm',
     [(225, 312), (262, 272), (300, 290), (340, 308), (390, 312), (425, 312), (425, 277), (497, 277), (497, 305),
      (475, 305), (475, 347), (260, 347)], None),
    ('Museum Store', 'space', 'Museum Store (while the plaza is rebuilt, the museum’s way in and out is through the '
     'store)', rect(306, 348, 404, 429), None),
    ('Restrooms L', 'space', 'Restrooms', rect(405, 347, 495, 428), None),
    ('Captain Paul Cuffe Park', 'space', f'Captain Paul Cuffe Park: an outdoor park honoring the merchant, whaler and '
     f'abolitionist {GUESS}', rect(790, 330, 1050, 460), None),
]
LOWER_CLOSED = []
LOWER_DOORS = [('Lobby', 'Theater', (246, 290)), ('Lobby', 'Whales Today', (360, 309)),
               ('Lobby', 'Local Artist Showcase', (406, 311)), ('Whales Today', 'Old Dartmouth Historical Society', (423, 200)),
               ('Lobby', 'Old Dartmouth Historical Society', (460, 276)), ('Lobby', 'Wattles Family Gallery', (498, 292)),
               ('Lobby', 'Museum Store', (355, 347)), ('Lobby', 'Restrooms L', (440, 347))]
LOWER_AMEN = [('entrance', 316, 395), ('info', 377, 330), ('elevator', 437, 290), ('coat', 462, 322), ('restroom', 450, 400),
              ('shop', 360, 375), ('stairs', 316, 252)]
LOWER_LABELS = [('Entrance and exit through the Museum Store ←', 250, 445),
                ('Captain Paul Cuffe Park (outdoors, approximate)', 920, 395)]
LOWER_NOTES = [('Emergency exit', 200, 140)]

# ---- Main Level (pixels of the self-guide's Main Level picture) ----------------------------------------------------

MAIN = [
    ('Whales Today ramp', 'corridor', 'Whales Today ramp: looks down on the whale skeletons; elevator to the Lobby',
     [(300, 400), (365, 322), (422, 360), (402, 394), (567, 394), (567, 355), (605, 355), (605, 440), (347, 440)], None),
    ('Rotating Exhibition 2', 'gallery', 'Rotating Exhibition 2 (Braitmayer Family Galleries)', rect(567, 145, 663, 268),
     'Rotating 2'),
    ('Rotating Exhibition 1', 'gallery', 'Rotating Exhibition 1', rect(567, 273, 663, 352), 'Rotating 1'),
    ('Rotating Exhibition 3', 'gallery', 'Rotating Exhibition 3 (Scrimshaw Gallery Annex)', rect(667, 145, 800, 213),
     'Rotating 3'),
    ('Scrimshaw Gallery', 'gallery', 'Scrimshaw Gallery: the largest scrimshaw collection in the world',
     rect(700, 215, 803, 298), 'Scrimshaw'),
    ('18th-Century Kitchen', 'gallery', '18th-Century Kitchen', rect(700, 298, 803, 353), 'Kitchen'),
    ('Harboring Hope', 'gallery', 'Harboring Hope in Old Dartmouth: the colonial history of the region. The ramp here '
     'leads toward the elevator to the Upper Level',
     [(605, 355), (665, 355), (665, 215), (698, 215), (698, 355), (800, 355), (800, 442), (605, 442)], 'Harboring Hope'),
    ('Harboring Hope east', 'corridor', 'Harboring Hope (continued)',
     [(800, 355), (877, 355), (877, 395), (970, 395), (970, 355), (1012, 355), (1012, 442), (800, 442)], None),
    ('Energy & Enterprise', 'gallery', 'Energy & Enterprise: Industry and the City of New Bedford (Gratia Houghton '
     'Rinehart Gallery)', rect(805, 145, 968, 353), 'Energy & Enterprise'),
    ('East Meets West', 'gallery', 'East Meets West (International Gallery), with the Kid’s Corner; elevator to the '
     'Upper Level', rect(970, 225, 1170, 355), 'East Meets West'),
    ('Captain Paul Cuffe', 'gallery', 'Captain Paul Cuffe: His Work, Vision, and Living Legacy', rect(1013, 357, 1170, 442),
     'Paul Cuffe'),
    ('Research Library', 'space', 'Research Library (open by appointment)', rect(1170, 157, 1433, 247), None),
    ('Classroom 1', 'space', 'Classroom 1', rect(1172, 250, 1265, 380), None),
    ('Classroom 2', 'space', 'Classroom 2', rect(1268, 250, 1364, 380), None),
    ('East corridor', 'corridor', 'Corridor: all-gender restroom, elevator, emergency exit',
     [(1170, 382), (1390, 382), (1390, 250), (1433, 250), (1433, 310), (1498, 310), (1498, 440), (1170, 440)], None),
    ('Cultures of Whaling', 'gallery', 'Cultures of Whaling (Dr. Roderick H. Turner Gallery): the sperm whale skeleton '
     'and The City that Lit the World', rect(406, 445, 697, 663), 'Cultures of Whaling'),
    ('Lagoda', 'gallery', 'A Whaling Voyage Around the World (Bourne Building): the Lagoda, the half-scale whaling '
     'ship you can board (7 steps up to the deck)', rect(697, 445, 1157, 663), 'Lagoda'),
]
MAIN_CLOSED = [
    # the two-storey Jacobs Family Gallery: open to the Lobby below, the skeletons hang here
    [(137, 230), (220, 145), (565, 145), (565, 392), (402, 392), (422, 360), (365, 322), (300, 400), (137, 400)],
    rect(877, 357, 968, 393),            # stair and emergency exit
    rect(970, 145, 1167, 222), rect(1437, 153, 1633, 310),
]
MAIN_DOORS = [('Whales Today ramp', 'Cultures of Whaling', (500, 442)), ('Whales Today ramp', 'Harboring Hope', (605, 420)),
              ('Harboring Hope', 'Rotating Exhibition 1', (664, 320)), ('Harboring Hope', 'Rotating Exhibition 2', (664, 240)),
              ('Harboring Hope', 'Rotating Exhibition 3', (682, 214)), ('Harboring Hope', 'Scrimshaw Gallery', (699, 255)),
              ('Harboring Hope', '18th-Century Kitchen', (699, 330)), ('Harboring Hope', 'Harboring Hope east', (800, 420)),
              ('Harboring Hope east', 'Energy & Enterprise', (840, 354)), ('Harboring Hope east', 'East Meets West', (990, 355)),
              ('Harboring Hope east', 'Captain Paul Cuffe', (1012, 420)), ('Harboring Hope east', 'Lagoda', (980, 443)),
              ('Harboring Hope', 'Lagoda', (720, 443)), ('Cultures of Whaling', 'Lagoda', (697, 600)),
              ('East Meets West', 'Research Library', (1170, 236)), ('Captain Paul Cuffe', 'East corridor', (1170, 410)),
              ('East corridor', 'Classroom 1', (1218, 381)), ('East corridor', 'Classroom 2', (1315, 381)),
              ('East corridor', 'Research Library', (1410, 249))]
MAIN_AMEN = [('elevator', 585, 373), ('elevator', 1032, 336), ('elevator', 1468, 333), ('restroom-all', 1453, 410),
             ('stairs', 725, 462), ('stairs', 725, 555), ('stairs', 725, 645)]
MAIN_LABELS = [('JACOBS FAMILY GALLERY (open to the Lobby below)', 350, 200), ('BOURNE BUILDING', 930, 690)]
MAIN_NOTES = [('Emergency exit', 427, 643), ('Emergency exit', 938, 643), ('Emergency exit', 922, 375),
              ('Emergency exit', 1411, 300), ('Ramp', 746, 377), ('Ramp', 983, 465)]

# ---- Upper Level (pixels of the self-guide's Upper Level picture) -------------------------------------------------

UPPER = [
    ('Lagoda balcony', 'gallery', 'A Voyage Around the World: the balcony around the Lagoda, from the Azores and Cape '
     'Verde to the Pacific and the Arctic',
     [(555, 343), (867, 343), (867, 506), (555, 506), (555, 472), (837, 472), (837, 388), (555, 388)], 'Voyage'),
    ('Rotating Exhibition UL', 'gallery', 'Upper-level galleries: special exhibitions; elevator to the Main Level',
     [(729, 225), (880, 225), (880, 297), (745, 297), (745, 343), (720, 343), (720, 277), (729, 277)], 'Upper Gallery'),
    ('Restrooms UL', 'space', 'Restrooms', rect(747, 298, 878, 340), None),
    ('Observation Deck', 'space', 'Observation Deck (outdoors)', rect(729, 177, 880, 223), None),
    ('Harbor View', 'space', 'Harbor View: a 180-degree view of New Bedford harbor. There is no café; you may eat your '
     'own food here and in the Lobby',
     [(880, 175), (1075, 175), (1075, 195), (1043, 195), (1043, 275), (1077, 275), (1077, 242), (1125, 242),
      (1125, 340), (880, 340)], None),
    ('Harbor View Terrace', 'space', 'Harbor View Terrace (outdoors)', rect(880, 128, 1075, 173), None),
]
UPPER_CLOSED = [rect(660, 275, 717, 302), rect(1043, 195, 1075, 275)]
UPPER_DOORS = [('Lagoda balcony', 'Rotating Exhibition UL', (732, 343)), ('Rotating Exhibition UL', 'Restrooms UL', (746, 320)),
               ('Rotating Exhibition UL', 'Observation Deck', (800, 224)), ('Rotating Exhibition UL', 'Harbor View', (880, 260)),
               ('Harbor View', 'Harbor View Terrace', (960, 174))]
UPPER_AMEN = [('elevator', 773, 260), ('elevator', 1100, 258), ('restroom', 807, 318),
              ('stairs', 562, 355), ('stairs', 562, 494)]
UPPER_LABELS = [('Acushnet River and the harbor ↑', 970, 110), ('Lagoda (below)', 700, 430)]
UPPER_NOTES = [('Emergency exit', 688, 290), ('Emergency exit', 1058, 235)]

PLACES = {   # names of the spaces that aren't galleries
    'L': [('Lobby', 330, 330), ('Museum Store', 355, 412), ('Restrooms', 450, 418)],
    'ML': [('Research Library', 1300, 200), ('Classroom 1', 1218, 300), ('Classroom 2', 1315, 300)],
    'UL': [('Harbor View', 985, 300), ('Observation Deck', 805, 200), ('Harbor View Terrace', 978, 150),
           ('Restrooms', 780, 330)],
}

LABEL_AT = {'Harboring Hope': (750, 405), 'Whales Today': (355, 150), 'Lagoda balcony': (700, 360),
            'Old Dartmouth Historical Society': (461, 175), 'Wattles Family Gallery': (550, 240)}


def inside(pt, poly):
    x, y = pt
    c = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c


def floor(fid, label, order, area, rooms, closed, doors, amen, labels, notes):
    m = MOVE[fid]
    mv = lambda q: P(*m(q[0], q[1]))
    rr = []
    for rid, kind, name, poly, short in rooms:
        r = {'id': rid, 'kind': kind, 'name': name, 'poly': [mv(q) for q in poly]}
        if kind == 'gallery': r['label'] = short
        if rid in LABEL_AT: r['labelAt'] = mv(LABEL_AT[rid])
        rr.append(r)
    return {'id': fid, 'label': label, 'order': order, 'transform': [0.25, 0, 0], 'area': area, 'rooms': rr,
            'closed': [{'poly': [mv(q) for q in c]} for c in closed],
            'amenities': [{'type': t, 'at': mv((x, y))} for t, x, y in amen],
            'labels': [{'text': t, 'kind': 'area', 'at': mv((x, y))} for t, x, y in labels]
                      + [{'text': t, 'kind': 'place', 'at': mv((x, y))} for t, x, y in PLACES[fid]],
            'notes': [{'text': t, 'kind': 'note', 'at': mv((x, y))} for t, x, y in notes],
            'doors': [{'a': a, 'b': b, 'at': mv(p), 'width': 16, 'axis': 'o'} for a, b, p in doors]}


def build_floors():
    floors = [
        floor('L', 'Lobby & Lower Level', 0, 'Entrance, tickets · Whales Today and the skeletons · Theater · Old '
              'Dartmouth · Wattles Gallery · Store',
              LOWER, LOWER_CLOSED, LOWER_DOORS, LOWER_AMEN, LOWER_LABELS, LOWER_NOTES),
        floor('ML', 'Main Level', 1, 'Lagoda · Cultures of Whaling · Scrimshaw · Harboring Hope · Energy & Enterprise · '
              'East Meets West · Paul Cuffe',
              MAIN, MAIN_CLOSED, MAIN_DOORS, MAIN_AMEN, MAIN_LABELS, MAIN_NOTES),
        floor('UL', 'Upper Level', 2, 'Lagoda balcony: A Voyage Around the World · Special exhibitions · Harbor View · '
              'Observation Deck',
              UPPER, UPPER_CLOSED, UPPER_DOORS, UPPER_AMEN, UPPER_LABELS, UPPER_NOTES),
    ]
    for f in floors:
        ids = [r['id'] for r in f['rooms']]
        assert len(ids) == len(set(ids)), f['id']
        for d in f['doors']:
            assert d['a'] in ids and d['b'] in ids, (f['id'], d)
        for a in f['amenities']:
            assert any(inside(a['at'], r['poly']) for r in f['rooms']), (f['id'], a)
    return {'about': 'Built by tools/build_nbwm.py. Traced from the New Bedford Whaling Museum’s own map of its three '
                     'levels (2026 self-guide and Visitors Guide): galleries, restrooms, elevators, stairs, emergency '
                     'exits, the store and information desk where the museum puts them. Walls are simplified; Captain '
                     'Paul Cuffe Park outside is placed roughly.',
            'source': 'New Bedford Whaling Museum, General Self Guide 2026 and Visitors Guide (maps)',
            'units': 'pixels of the museum’s Main Level map picture x 2; the harbor is at the top',
            'approximate': False, 'defaultFloor': 'L', 'galleryWord': 'Gallery', 'floors': floors}


# ---- works -------------------------------------------------------------------------------------------------------

def text_of(c):
    c = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', c, flags=re.S)
    return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', c))).strip()


def picture(key, url):
    if not url: return None
    raw = CACHE / 'img' / f'{key}.bin'
    if not raw.exists():
        raw.parent.mkdir(parents=True, exist_ok=True)
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '90', '-A', UA, url], capture_output=True).stdout
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
    return f'data/nbwm/images/{key}.jpg'


def slugify(s, n=60):
    return re.sub(r'-+', '-', re.sub(r'[^a-z0-9]+', '-', s.lower())).strip('-')[:n].strip('-')


# Exhibitions on view: post slug -> (room, placed by guess?, kind, closing date or None)
EXHIBITIONS = {
    'lagoda': ('Lagoda', False, 'Permanent gallery', None),
    'a-voyage-around-the-world': ('Lagoda balcony', False, 'Permanent gallery', None),
    'scrimshaw': ('Scrimshaw Gallery', False, 'Permanent gallery', None),
    'east-meets-west': ('East Meets West', False, 'Permanent gallery', None),
    'captain-paul-cuffe': ('Captain Paul Cuffe', False, 'Permanent gallery', None),
    'old-dartmouth-historical-society': ('Old Dartmouth Historical Society', False, 'Permanent gallery', None),
    'harboring-hope': ('Harboring Hope', False, 'Permanent gallery', None),
    'energy-enterprise-industry-and-the-city-of-new-bedford': ('Energy & Enterprise', False, 'Permanent gallery', None),
    'forging-independence-building-a-nation': ('Rotating Exhibition 2', True, 'Long-term exhibition', None),
    'sailors-valentines-maritime-art-from-the-heart': ('Rotating Exhibition UL', False, 'Special exhibition', 'November 8, 2026'),
    'boundless-the-book-as-art': ('Wattles Family Gallery', False, 'Special exhibition', 'February 15, 2027'),
    'coquilla-nut-carvings-an-afro-brazilian-artform': ('Rotating Exhibition 3', True, 'Special exhibition', 'February 1, 2027'),
    'bristol-county-incarcerated': ('Rotating Exhibition 1', True, 'Special exhibition', 'April 11, 2027'),
    'local-artist-showcase': ('Local Artist Showcase', False, 'Rotating display', None),
}
WHERE_POST = {   # what the museum's page says about where the exhibition is, for the place note
    'forging-independence-building-a-nation': 'the Braitmayer Family Galleries',
    'coquilla-nut-carvings-an-afro-brazilian-artform': 'the Scrimshaw Gallery Annex',
    'bristol-county-incarcerated': 'no gallery name',
}

# Permanent Exhibitions page sections that are not exhibition posts: title -> (room, guessed)
SECTIONS = {
    'Exploring Our Ecosystem: Climate Change, Whales, and Us': ('Whales Today', True),
    '18ᵗʰ century Kitchen': ('18th-Century Kitchen', False),
    'Kid’s Corner': ('East Meets West', False),
    'Sailor’s nook': ('Lagoda', False),
    'The City that Lit the World': ('Cultures of Whaling', False),
}
SECTION_TITLE = {'18ᵗʰ century Kitchen': '18th-Century Kitchen', 'Sailor’s nook': 'Sailor’s Nook'}

# The museum's best-known things, written for this guide from its pages and guides.
# (key, room, title, kind, text, (page id or exhibition slug, picture file name part) or None, source url)
HIGHLIGHTS = [
    ('lagoda-model', 'Lagoda', 'Lagoda, the half-scale whaling bark', 'Ship model',
     'The largest ship model in existence: a half-size copy of the New Bedford whaling bark Lagoda, built inside the '
     'Bourne Building in 1915–16 with money from Emily Bourne in memory of her father, whaling merchant Jonathan '
     'Bourne Jr. You can step aboard (7 steps up to the deck); look up the masts for the hoops where lookouts stood.',
     ('lagoda', 'Lagoda-1536x1152'), f'{SITE}/exhibition/lagoda/'),
    ('kobo', 'Whales Today', 'Kobo, the blue whale skeleton', 'Whale skeleton',
     'A 66-foot juvenile male blue whale, struck by a tanker off Nova Scotia and carried into Narragansett Bay in '
     '1998. Its skeleton is the centerpiece of the Jacobs Family Gallery, hanging over the Lobby (you also see it from '
     'the Whales Today ramp on the Main Level). Only some 500 blue whales live in the North Atlantic.',
     (2531, 'kobo'), f'{SITE}/research/research-resources/whale-science/biology/skeletons-of-the-deep/blue-whale/'),
    ('quasimodo', 'Whales Today', 'Quasimodo, the humpback whale skeleton', 'Whale skeleton',
     'A 37-foot male humpback, about 3 years old, that died in 1932 and was towed ashore in Westport. He has hung in '
     'the museum since 1936, first next to the Lagoda, and in the Jacobs Family Gallery since 2000.',
     (2531, 'quas'), f'{SITE}/research/research-resources/whale-science/biology/skeletons-of-the-deep/humpback-whale/'),
    ('reyna', 'Whales Today', 'Reyna, the North Atlantic right whale, and her unborn calf', 'Whale skeleton',
     'A 49-foot, 15-year-old female right whale, ten months pregnant with her first calf when a ship struck her in '
     'Chesapeake Bay. Her skeleton was hoisted to the Jacobs Family Gallery ceiling in 2008, with her calf’s beside '
     'her. Right whales are among the most endangered whales in the world.',
     (2531, 'reyna-1'), f'{SITE}/research/research-resources/whale-science/biology/skeletons-of-the-deep/north-atlantic-right-whale/'),
    ('blue-whale-heart', 'Whales Today', 'Life-size blue whale heart', 'Model',
     'A full-size model of a blue whale’s heart, the largest heart of any animal. The museum’s guide asks: how many '
     'people could safely fit inside it? It arrived in 2018 as the first piece of the new Whales Today gallery.',
     None, f'{SITE}/visit/'),
    ('sperm-whale', 'Cultures of Whaling', 'Sperm whale skeleton', 'Whale skeleton',
     'A 48-foot male sperm whale, about 30 years old, found stranded on Nantucket in 2002 and put together in this '
     'gallery, in front of visitors, in 2003–05. Look for the teeth that sperm whales use to catch giant squid: the '
     'oil of whales like him lit the world in the 1800s.',
     (2554, '2019.2.19-family-sperm-whale-turner-gallery'),
     f'{SITE}/research/research-resources/whale-science/biology/skeletons-of-the-deep/sperm-whale/'),
    ('plastic-scrimshaw', 'Scrimshaw Gallery', 'No. 384 of the Poly S. Tyrene Memorial Maritime Museum', 'Object',
     'Duke Riley (American, b. 1972), 2023. A plastic coolant jug found on a beach clean-up, etched to look like '
     'scrimshaw: a factory spews waste into the water under a banner with the names of the companies that polluted '
     'the Acushnet River. The museum asks: should this be called scrimshaw, too? NBWM 2023.71.',
     (7877, 'IMG_6557'), f'{SITE}/plastic-scrimshaw/'),
    ('vigia', 'Lagoda balcony', 'The Vigia', 'Object',
     'A white lookout hut like those used in the Azores to spot whales from land. Look through its telescope for a '
     'whale; nearby you can listen to music, poems and stories in Crioulo, Portuguese and English about Cape '
     'Verdean culture.', None, f'{SITE}/exhibition/a-voyage-around-the-world/'),
    ('whales-today', 'Whales Today', 'Whales Today', 'Permanent gallery',
     'Dedicated to the science and behavior of whales, the threats they face today, ocean preservation and marine '
     'mammal conservation: bioacoustics, tagging, the sand table and an augmented-reality whale.', None, f'{SITE}/visit/'),
    ('cultures-of-whaling', 'Cultures of Whaling', 'Cultures of Whaling', 'Permanent gallery',
     'The geography, environment and habitats behind the hunting of whales for food, bones and oil around the world.',
     None, f'{SITE}/visit/'),
    ('theater', 'Theater', 'The 3D movie', 'Theater',
     'A 3D movie about the natural world, every half hour from 10:30 to 2:30. $6 ($4 for members or with museum '
     'admission); ask at the Admission Desk.', None, f'{SITE}/visit/'),
    ('harbor-view', 'Harbor View', 'Harbor View', 'View',
     'A 180-degree view over New Bedford harbor and the Acushnet River: the highest-grossing commercial fishing port in '
     'the United States. Listen and look: what connects to the city’s history?', None, f'{SITE}/visit/'),
]

CAPTION_FIX = {   # captions that the simple reader below splits wrongly: caption start -> (artist, title, year)
    'Duke Riley, Sailor': ('Duke Riley', 'Sailor’s Valentine', 'ca. 2023'),
    'Ralph Cahoon and Bernard Woodman': ('Ralph Cahoon and Bernard Woodman', 'A Whale of a Valentine', 'ca. 1979'),
    'Bernard Woodman Sailors': ('Bernard Woodman', 'Sailor’s Valentine with a Small Heart', '1977'),
    'Kuniyoshi, Miyamoto': ('Utagawa Kuniyoshi', 'Miyamoto Musashi and the Whale', 'ca. 1848–1852'),
    'Kuniyoshi, Catching': ('Utagawa Kuniyoshi', 'Catching Whales at Goto and Hirado and Kishu', 'ca. 1840'),
    'Shuntei Katsukawa': ('Katsukawa Shuntei', 'Seeing the whale in Shinagawa Bay at Takanawa', 'ca. 1798'),
    'James Steward': ('James Steward and William Home Lizars', 'The Spermaceti Whale', '1837'),
    'Clifford Warren Ashley': ('Clifford Warren Ashley', 'Lowering Boats', '1927'),
    'Print of the Wanderer': ('Artist unknown', 'The Wanderer sailing in open seas', 'ca. 1922'),
    'Scene of the Azores': ('Benjamin Russell and Caleb Purrington', 'Scene of the Azores, from the Grand Panorama', '1848'),
    'This thirty-two point': ('Isaac Greenwood', 'Paul Cuffe’s compass', '1780'),
    'Barthelemy Lauvergne': ('Barthélemy Lauvergne and Léon Jean-Baptiste Sabatier', 'Vue de Rio Janeiro, Brésil', 'ca. 1840'),
}
CAPTION_FIX.update({
    'John Harrison Curtis': ('John Harrison Curtis (British, 1778-1860)', 'A treatise on the physiology and diseases of '
                             'the eye', '1835'),
    'Shawn Sheehy': ('Shawn Sheehy', 'Beyond the 6th Extinction', '2007'),
    '“Wamsutta Mills,”': ('William Allen Wall', 'Wamsutta Mills', '1851'),
    '“Captain Paul Cuffe 1812”': ('Thomas Pole', 'Captain Paul Cuffe, 1812', 'ca. 1820s'),
})
DEFAULT_ARTIST = {'coquilla-nut-carvings-an-afro-brazilian-artform': 'Maker once known'}
TITLE_FIX = {'sailors-valentines-maritime-art-from-the-heart': 'Sailor’s Valentines: Maritime Art from the Heart',
             'lagoda': 'The Lagoda gallery: going a-whaling'}
TEXT_FROM_SECTION = {'old-dartmouth-historical-society': 'The Old Dartmouth Historical Society'}
SKIP_CAPTIONS = ('Detail of Cuffe',)
SKIP_EXACT = {'Maker once known,'}


def split_caption(cap):
    for start, (artist, title, year) in CAPTION_FIX.items():
        if cap.startswith(start): return artist, title, year
    m = re.match(r'^(.*?\)|[^,]*?maker once known|Maker once known)\s*,\s*(.+?),\s*((?:ca\.\s*|c\.\s*)?\d{4}[^.,]*)[.,]', cap)
    if m:
        title = re.sub(r'^Author,\s*', '', m[2].strip(' .'))
        title = re.sub(r'^et\.?\s*al\.?,?\s*', '', title)
        title = re.split(r',\s*[A-Z][\w ]+:\s', title)[0].rstrip(' :,…')
        return m[1].strip(), title, m[3].strip()
    m = re.match(r'^(.+?),\s*ca\.\s*(\d{4})', cap)
    if m: return None, m[1].strip(), f'ca. {m[2]}'
    return None, cap.split('. ')[0][:120], None


def year_num(y):
    m = re.search(r'\d{4}', y or '')
    return int(m[0]) if m else None


def accession(cap):
    m = re.search(r'\b((?:19|20)\d\d\.\d+(?:\.\d+)*[A-Z]?|00\.\d+\.\d+)\b(?!.*\b(?:19|20)\d\d\.\d)', cap)
    return m[1] if m else None


def captioned(content):
    """(image url, caption) pairs of an exhibition page, in order, without repeats."""
    out, seen = [], set()
    for m in re.finditer(r'<a\b[^>]*?href="([^"]+\.(?:jpe?g|png))"[^>]*?data-caption="([^"]*)"', content, re.I):
        url, cap = m[1], html.unescape(m[2]).strip()
        if not cap:
            after = content[m.end():m.end() + 2000]
            after = after[after.find('>') + 1:]
            cap = text_of(after.split('</a>')[0])
        cap = re.sub(r'\s+', ' ', cap).strip()
        if not cap or cap in seen or cap in SKIP_EXACT or cap.startswith(SKIP_CAPTIONS): continue
        seen.add(cap)
        out.append((url, cap))
    return out


def page(pid):
    return json.loads((CACHE / f'page-{pid}.json').read_text())


def build_works(floors):
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    path = CACHE / 'exhibitions.json'
    if not path.exists(): raise SystemExit('run tools/harvest_nbwm.py first')
    posts = {p['slug']: p for p in json.loads(path.read_text())}
    works = []

    def add(a, room, guessed, note):
        fl, gname = rooms[room]
        a.update({'gallery': room, 'galleryName': gname, 'floor': fl, 'placeNote': note})
        if guessed: a['placeGuessed'] = True
        works.append({k: v for k, v in a.items() if v not in (None, '')})

    # 1. the galleries and exhibitions on view
    perm = page(5574)['content']['rendered']
    sections = re.findall(r'<img[^>]+src="([^"]+)"[^>]*>.*?<h2>\s*(.*?)\s*</h2>\s*<p>(.*?)</p>', perm, re.S)
    section_by_title = {html.unescape(t).strip(): (img, text_of(p)) for img, t, p in sections}
    for slug, (room, guessed, kind, closes) in EXHIBITIONS.items():
        p = posts[slug]
        title = TITLE_FIX.get(slug) or text_of(p['title']['rendered'])
        body = text_of(p['content']['rendered'])
        # the post repeats its title, gallery and dates before the text; start at the first long sentence
        excerpt = text_of(p['excerpt']['rendered'])
        if slug in TEXT_FROM_SECTION: excerpt = section_by_title[TEXT_FROM_SECTION[slug]][1]
        imgs = re.findall(r'<img[^>]+src="([^"]+\.(?:jpe?g|png))"', p['content']['rendered'], re.I)
        key = f'nbwm-{slug[:50]}'
        a = {'id': key, 'title': title, 'artist': kind, 'description': (excerpt or body)[:1200], 'url': p['link'],
             'image': picture(key, imgs[0] if imgs else None)}
        if closes:
            a['description'] = a['description'].rstrip(' .') + f'. On view until {closes}.'
            a['temporary'] = True
        if a['image']: a['imageCredit'] = 'New Bedford Whaling Museum (whalingmuseum.org)'
        note = (f'The museum’s page names {WHERE_POST[slug]}; which room on the map is our guess.' if guessed
                else 'Where the museum’s map and page put it.')
        add(a, room, guessed, note)
    for title, (room, guessed) in SECTIONS.items():
        img, text = section_by_title[title]
        t = SECTION_TITLE.get(title, title)
        key = f'nbwm-{slugify(t)}'
        a = {'id': key, 'title': t, 'artist': 'Permanent gallery', 'description': text, 'url': f'{SITE}/exhibitions/permanent/',
             'image': picture(key, img), 'imageCredit': 'New Bedford Whaling Museum (whalingmuseum.org)'}
        note = ('Where the museum’s self-guide puts it.' if not guessed else
                'The museum doesn’t say which room; we put it with Whales Today, where the self-guide sends you to learn '
                'about whales and ecology.')
        add(a, room, guessed, note)

    # 2. the best-known things
    for key, room, title, kind, text, pic, url in HIGHLIGHTS:
        a = {'id': f'nbwm-{key}', 'title': title, 'artist': kind, 'description': text, 'url': url}
        if pic:
            src, part = pic
            content = page(src)['content']['rendered'] if isinstance(src, int) else posts[src]['content']['rendered']
            hit = next((u for u in re.findall(r'(?:src|href)="([^"]+\.(?:jpe?g|png))"', content, re.I) if part in u), None)
            a['image'] = picture(f'nbwm-{key}', hit)
            if a['image']: a['imageCredit'] = 'New Bedford Whaling Museum (whalingmuseum.org)'
        add(a, room, False, 'Where the museum’s map and guides put it.')

    # 3. objects pictured, with captions, on the pages of the exhibitions on view
    for slug, (room, guessed, kind, closes) in EXHIBITIONS.items():
        p = posts[slug]
        ex_title = text_of(p['title']['rendered'])
        for url, cap in captioned(p['content']['rendered']):
            artist, title, year = split_caption(cap)
            artist = artist or DEFAULT_ARTIST.get(slug)
            if len(title) > 70:      # long descriptive titles: keep the first phrase, the caption has the rest
                cut = title.find(', ', 30)
                title = title[:cut] if 0 < cut <= 90 else title[:80].rsplit(' ', 1)[0] + '…'
            acc = accession(cap)
            key = f'nbwm-{slugify(acc or title, 50)}'
            if any(w['id'] == key for w in works): key += '-2'
            a = {'id': key, 'title': title, 'artist': artist, 'year': year_num(year), 'date': year,
                 'description': cap, 'url': p['link'], 'accession': acc, 'image': picture(key, url),
                 'exhibition': ex_title}
            if a['image']: a['imageCredit'] = 'New Bedford Whaling Museum (whalingmuseum.org)'
            if closes: a['temporary'] = True
            note = (f'Shown in {ex_title}; which room on the map is our guess.' if guessed
                    else f'Shown in {ex_title}.')
            add(a, room, guessed, note)

    order = {r['id']: i for f in floors['floors'] for i, r in enumerate(f['rooms'])}
    forder = {f['id']: f['order'] for f in floors['floors']}
    rank = {'Permanent gallery': 0, 'Long-term exhibition': 0, 'Special exhibition': 0, 'Rotating display': 0}
    works.sort(key=lambda a: (forder[a['floor']], order[a['gallery']], rank.get(a.get('artist'), 1), a['title']))
    return {'source': 'New Bedford Whaling Museum: exhibition pages, whale skeleton pages and visitor guides '
                      '(whalingmuseum.org)',
            'checked': time.strftime('%Y-%m-%d'), 'count': len(works), 'complete': False, 'artworks': works}


def build_guide(works):
    rows = []
    for a in works['artworks']:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a.get('artist'), 'year': a.get('year'),
                     'url': a['url'], 'imageUrl': a.get('image'), 'onView': True,
                     'gallery': a['gallery'], 'floor': a['floor']}.items() if v not in (None, '')})
    return {'museum': MUSEUM, 'name': NAME, 'checked': time.strftime('%Y-%m-%d'),
            'source': 'New Bedford Whaling Museum: exhibition pages and visitor guides (whalingmuseum.org)',
            'onViewKnown': True,
            'note': 'The museum holds some 750,000 objects, and its collection database is closed to programs like this '
                    'one. Listed here are its galleries and exhibitions on view, its whale skeletons and the Lagoda, and '
                    'the objects the museum pictures on the pages of the exhibitions on view now, in the rooms where '
                    'its map puts them.',
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
    print(f'{works["count"]} galleries, skeletons and objects ({sum("image" in a for a in works["artworks"])} with pictures)')
    for k, v in by.items(): print(f'  {k}: {v}')


if __name__ == '__main__':
    sys.exit(main())
