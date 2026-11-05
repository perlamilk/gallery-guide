#!/usr/bin/env python3
"""Build the USS Constitution Museum + USS Constitution map guide (run: python3 tools/build_constitution.py).

    data/constitution/floors.json      a flat 2D map: the Navy Yard with the museum's first floor, the museum's
                                       second floor, and the ship's three visitor decks
    data/constitution/artworks.json    what you see in each gallery and on each deck
    data/constitution/images/          pictures, made smaller for phones
    data/guides/Q7868542.json          the same list for the museum page, plus the museum's online collection

Where the information comes from
--------------------------------
The museum (a private non-profit in Building 22, the old pump house at the head of Dry Dock 1 in the Charlestown
Navy Yard) and the ship (an active-duty U.S. Navy ship at Pier 1, run separately by the Navy) are one visit.

  * Navy Yard: OpenStreetMap (api.openstreetmap.org, ODbL) outlines of the museum building, the National Park
    Service Visitor Center (Building 5), Dry Dock 1, Pier 1, USS Cassin Young and the small building on Pier 1 where
    the Navy screens visitors (Building 292, from the Park Service's rules; which building it is is approximate),
    set on Esri World Imagery at zoom 19. The whole map is turned 33.7 degrees so that Pier 1 and the ship run left
    to right: map "up" is north-east. Units are imagery pixels (about 0.22 m).
  * The museum: its own visitor map in "My Visit to the USS Constitution Museum" (social narrative, Sept 2024,
    page 5: first and second floors with stairs, elevator, restrooms, fire exits). It is a diagram, so it is drawn
    about twice life size where the building stands. Room names are updated to the exhibits the museum lists
    in 2026 (ussconstitutionmuseum.org/exhibits): the old Today's Navy room is now the Special Exhibition Gallery
    (a guess, from the press release on its "renewed" gallery), Art of the Ship is in the theater.
  * The ship: a diagram, drawn large, of the three decks visitors see on the Navy's tour (spar, gun and berth deck),
    from the museum's descriptions of the ship. She is turned around every year to weather evenly, so her bow may
    point the other way.

The works: the exhibits from the museum's exhibits page and social narratives, the ship's features from the
museum's ship facts and blog, and the museum's online collection (about 205 objects, read slowly by
tools/harvest_constitution.py) on the museum page, as not known to be on view.
"""
import io
import json
import math
import re
import subprocess
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'constitution'
CACHE = ROOT / '.cache' / 'constitution'
MUSEUM = 'Q7868542'
NAME = 'USS Constitution Museum'
SITE = 'https://ussconstitutionmuseum.org'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
CHECKED = time.strftime('%Y-%m-%d')
WALK = 0.63            # map unit (0.22 m) -> router point (0.35 m)
SHIP_WALK = 0.24       # the ship is drawn about 2.6 times life size
SCALE = 0.5              # map units -> app units (text and icons keep their size, so the map is drawn smaller)
_last = [0.0]


def get(url, dest, delay=10):
    """Read a file once, politely (the museum asks for 10 s between requests), and keep it."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0: return dest
    wait = _last[0] + delay - time.time()
    if wait > 0: time.sleep(wait)
    subprocess.run(['curl', '-s', '-f', '-L', '-m', '90', '-A', UA, '-o', str(dest), url])
    _last[0] = time.time()
    return dest if dest.exists() and dest.stat().st_size > 0 else None


# ---- the frame: Esri imagery zoom 19, turned so Pier 1 runs left to right ----------------------------------------
Z, TX0, TY0 = 19, 158657, 193887
W, H, RW, RH, CX, CY = 2560, 2304, 3410, 3338, 1000, 900
ANG = math.radians(33.690067525979785)


def frame(lon, lat):
    x = (lon + 180) / 360 * 2 ** Z * 256 - TX0 * 256
    r = math.radians(lat)
    y = (1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2 * 2 ** Z * 256 - TY0 * 256
    dx, dy = x - W / 2, y - H / 2
    return [round(RW / 2 + math.cos(ANG) * dx + math.sin(ANG) * dy - CX, 1),
            round(RH / 2 - math.sin(ANG) * dx + math.cos(ANG) * dy - CY, 1)]


def osm():
    f = get('https://api.openstreetmap.org/api/0.6/map?bbox=-71.0590,42.3705,-71.0525,42.3745', CACHE / 'yard.osm', 1)
    root = ET.fromstring(f.read_bytes())
    nodes = {n.get('id'): (float(n.get('lon')), float(n.get('lat'))) for n in root.findall('node')}
    ways = {}
    for w in root.findall('way'):
        pts = [frame(*nodes[n.get('ref')]) for n in w.findall('nd')]
        if pts and pts[0] == pts[-1]: pts = pts[:-1]
        ways[w.get('id')] = pts
    return ways


def rect(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def door(a, b, at, width=12):
    return {'a': a, 'b': b, 'at': [round(at[0], 1), round(at[1], 1)], 'width': width, 'axis': 'o'}


# ---- the museum: its own 2024 visitor map (page 5 of the social narrative, measured at 2000 px wide) -------------
def D(x, y):
    return [round(240 + (x - 1315) * 1.0, 1), round(497 - (1305 - y) * 1.0, 1)]


def DR(x0, y0, x1, y1):
    return [D(x0, y0), D(x1, y0), D(x1, y1), D(x0, y1)]


def DP(pts):
    return [D(x, y) for x, y in pts]


G, S, C = 'gallery', 'space', 'corridor'
STAIRS_AT, ELEV_AT = D(1492, 578), D(1525, 578)

MUSEUM_1 = [
    ('Lobby', S, None, 'Lobby and admission desk: everyone checks in here (suggested admission)', DR(1480, 1145, 1830, 1300)),
    ('Museum Store', S, None, 'Museum Store, next to the front doors', DR(1320, 1100, 1475, 1300)),
    ('Special Exhibition Gallery', G, 'Special Exhibits',
     'Special Exhibition Gallery: the renewed gallery for changing shows, with daylight and the old pump house’s '
     'structure', DP([(1320, 940), (1350, 900), (1440, 900), (1475, 930), (1475, 1095), (1320, 1095)])),
    ('War and Peace Hall', G, 'War and Peace',
     '“Old Ironsides” in War and Peace: the long hall, from the ship’s building to the War of 1812',
     DR(1480, 690, 1555, 1145)),
    ('War and Peace North', G, 'War and Peace',
     '“Old Ironsides” in War and Peace: battle, diplomatic voyages and preservation, with the cannon room',
     DR(1430, 535, 1740, 690)),
    ('Model Shop', G, 'Model Shop', 'Model Shop of the USS Constitution Model Shipwright Guild (windows onto the bench)',
     DR(1740, 600, 1835, 690)),
    ('Courtyard', S, None, 'Courtyard (open air): the quietest place in the museum', DR(1560, 695, 1830, 835)),
    ('Restrooms', S, None, 'Restrooms and water fountain (a family restroom on request at the admission desk)',
     DR(1560, 850, 1725, 930)),
    ('Theater', G, 'Theater', 'Theater: Art of the Ship (and the museum’s films)', DR(1560, 935, 1725, 1035)),
    ('Education Center', S, None, 'Education Center (school groups and programs)', DR(1560, 1040, 1725, 1140)),
]
MUSEUM_1_DOORS = [('Lobby', 'Museum Store', (1478, 1220)), ('Lobby', 'War and Peace Hall', (1517, 1145)),
                  ('War and Peace Hall', 'Special Exhibition Gallery', (1478, 1010)),
                  ('War and Peace Hall', 'Restrooms', (1557, 890)), ('War and Peace Hall', 'Theater', (1557, 985)),
                  ('War and Peace Hall', 'Education Center', (1557, 1090)),
                  ('War and Peace Hall', 'Courtyard', (1557, 760)),
                  ('War and Peace Hall', 'War and Peace North', (1517, 690)),
                  ('War and Peace North', 'Model Shop', (1740, 645))]
MUSEUM_STAFF_1 = [DR(1740, 535, 1835, 600)]

# second floor: the map draws it above the first; here it sits over the north wing, stairs over stairs
MUSEUM_2 = [
    ('All Hands on Deck', G, 'All Hands on Deck',
     'All Hands on Deck: A Sailor’s Life in 1812 (hands-on: scrub the deck, swing in a hammock, furl a sail)',
     DP([(1430, 535), (1550, 535), (1550, 610), (1650, 610), (1650, 535), (1835, 535), (1835, 695), (1430, 695)])),
    ('Battle Theater', G, 'Theater', 'Battle Theater: the film of a famous battle of 1812',
     DR(1550, 535, 1650, 610)),
]
MUSEUM_2_DOORS = [('All Hands on Deck', 'Battle Theater', (1600, 610))]


# ---- the ship: a diagram, drawn large over the water by Pier 1 (stern west, bow east) ------------------------------
Y0, Y1, YC = 1200, 1390, 1295
HULL_STERN = [[300, 1215], [320, 1204]]
HULL_STERN_B = [[320, 1386], [300, 1375]]
BOW = [[940, 1200], [1000, 1215], [1040, 1245], [1062, 1295], [1040, 1345], [1000, 1375], [940, 1390]]


def stern_room(x):
    return HULL_STERN + [[x, Y0 + 3], [x, Y1 - 3]] + HULL_STERN_B


def mid_room(x0, x1):
    return [[x0, Y0 + 2], [x1, Y0 + 1], [x1, Y1 - 1], [x0, Y1 - 2]]


def bow_room(x0):
    return [[x0, Y0 + 1]] + BOW + [[x0, Y1 - 1]]


LADDER_AFT, LADDER_MAIN = [470, 1245], [700, 1245]
SHIP_NOTE = 'Diagram, drawn large: the ship is 204 ft (62 m) long. She is turned around every year, so the bow may point the other way'

SPAR = [('Quarterdeck', G, 'Quarterdeck', 'Quarterdeck: the double wheel, the mizzenmast and the officers’ deck',
         stern_room(560)),
        ('Spar Deck Waist', G, 'Spar deck', 'Spar deck (the top deck), amidships: the mainmast, the carronades and the '
         'hatch down to the gun deck', mid_room(560, 820)),
        ('Forecastle', G, 'Forecastle', 'Forecastle at the bow: the foremast, the bell and the anchors', bow_room(820))]
GUN = [('Captain’s Cabin', G, 'Captain’s cabin', 'Captain’s cabin at the stern: the great cabin, the dining cabin and '
        'the sleeping cabins (seen from the door)', stern_room(420)),
       ('Gun Deck', G, 'Gun deck', 'Gun deck: thirty 24-pounder long guns, fifteen a side, the capstan and the pumps',
        mid_room(420, 930)),
       ('Galley', G, 'Galley', 'Galley stove and the bow (the manger)', bow_room(930))]
BERTH = [('Wardroom', G, 'Wardroom', 'Wardroom and the officers’ staterooms', stern_room(470)),
         ('Berth Deck', G, 'Berth deck', 'Berth deck: where some 450 sailors slung their hammocks', mid_room(470, 900)),
         ('Sick Bay', G, 'Sick bay', 'Sick bay and stores, in the bow', bow_room(900))]


def deck(spec):
    rooms = [{'id': rid, 'kind': k, 'label': lab, 'name': name, 'poly': pg, 'z': 1} for rid, k, lab, name, pg in spec]
    doors = []
    for a, b in zip(rooms, rooms[1:]):
        x = max(p[0] for p in a['poly'])
        doors.append(door(a['id'], b['id'], (x, YC), 14))
    return rooms, doors


def ship_labels():
    return [{'text': 'Stern', 'kind': 'note', 'at': [270, YC]}, {'text': 'Bow', 'kind': 'note', 'at': [1095, YC]},
            {'text': SHIP_NOTE, 'kind': 'note', 'at': [680, 1430]}]


# ---- the Navy Yard ----------------------------------------------------------------------------------------------
YARD_WALK = [[150, 497], [610, 497], [470, 528], [430, 548], [410, 572], [403, 600], [410, 630], [444, 646],
             [805, 752], [830, 800], [935, 853], [628, 1022], [604, 1022], [344, 1179], [238, 1157], [267, 1035],
             [318, 903], [254, 878], [150, 870]]


def yard_floor(ways):
    rooms = [{'id': 'Navy Yard', 'kind': C, 'name': 'Charlestown Navy Yard: the walk from the museum to Pier 1 '
              '(the Freedom Trail’s red line)', 'poly': YARD_WALK, 'labelAt': [280, 640], 'z': 0},
             {'id': 'Pier 1', 'kind': C, 'name': 'Pier 1 (inside the Navy’s security area)', 'poly': ways['605950516'],
              'labelAt': [1000, 1080], 'z': 0},
             {'id': 'Gangway', 'kind': C, 'name': 'Brow (gangway) onto the spar deck', 'poly': rect(590, 1172, 630, 1204),
              'z': 1},
             {'id': 'Security Screening', 'kind': S, 'label': 'Security',
              'name': 'Navy security screening for the ship (photo ID for 18 and over; Building 292, approximate)',
              'poly': ways['212123492'], 'z': 2},
             {'id': 'Visitor Center', 'kind': S, 'label': 'Visitor Center',
              'name': 'Charlestown Navy Yard Visitor Center (National Park Service, Building 5): rangers, exhibits, '
                      'restrooms', 'poly': ways['29739931'], 'z': 2},
             {'id': 'USS Cassin Young', 'kind': G, 'label': 'USS Cassin Young',
              'name': 'USS Cassin Young (DD-793), a World War II destroyer run by the National Park Service',
              'poly': ways['173838926'], 'z': 2}]
    for rid, k, lab, name, pg in MUSEUM_1:
        r = {'id': rid, 'kind': k, 'name': name, 'poly': pg, 'z': 2}
        if lab: r['label'] = lab
        rooms.append(r)
    sr, sd = deck(SPAR)
    rooms += sr
    doors = [door(a, b, D(*at)) for a, b, at in MUSEUM_1_DOORS] + sd
    doors += [door('Navy Yard', 'Lobby', D(1505, 1300), 16),
              door('Navy Yard', 'Visitor Center', (288, 891), 14),
              door('Navy Yard', 'Security Screening', (612, 1021), 14),
              door('Security Screening', 'Pier 1', (626, 1060), 14),
              door('Pier 1', 'Gangway', (610, 1175), 14), door('Gangway', 'Spar Deck Waist', (610, 1203), 14),
              door('Pier 1', 'USS Cassin Young', (1200, 925), 14)]
    amen = [('entrance', *D(1505, 1290)), ('info', *D(1650, 1200)), ('shop', *D(1400, 1200)),
            ('restroom', *D(1640, 890)), ('stairs', *STAIRS_AT), ('elevator', *ELEV_AT),
            ('restroom', 291, 931), ('info', 250, 960), ('entrance', 610, 1186),
            ('stairs', *LADDER_AFT), ('stairs', *LADDER_MAIN)]
    labels = [('Dry Dock 1 (1833)', 'area', 690, 690),
              ('Boston Harbor', 'area', 1300, 1420),
              ('↑ North-east: the map is turned to follow Pier 1', 'note', 1180, 560),
              ('Museum drawn from its own visitor map, about twice life size', 'note', 500, -300),
              ('Gate 1 · Constitution Road ←', 'note', 120, 1120),
              ('Nautica Parking Garage, 88 Constitution Rd (museum validates) ↙', 'note', 150, 1500),
              ('Ferry F4 to Long Wharf: Pier 4 ↗', 'note', 1350, 700)]
    return {'id': '1', 'label': 'Floor 1 · Navy Yard · Spar Deck', 'order': 0,
            'area': 'Museum first floor (lobby, store, exhibits, restrooms) · the Navy Yard · Pier 1 and the ship’s top '
                    'deck', 'transform': [SCALE, 0, 0], 'walkScale': WALK, 'rooms': rooms, 'doors': doors,
            'closed': [{'poly': p} for p in MUSEUM_STAFF_1] + [{'poly': ways['226524669']}],
            'amenities': [{'type': t, 'at': [x, y]} for t, x, y in amen],
            'labels': [{'text': t, 'kind': k, 'at': [x, y]} for t, k, x, y in labels] + ship_labels(),
            'homeView': ['Lobby', 'Museum Store', 'War and Peace North', 'Model Shop', 'Visitor Center', 'Quarterdeck',
                         'Forecastle']}


def museum_2_floor():
    rooms = []
    for rid, k, lab, name, pg in MUSEUM_2:
        r = {'id': rid, 'kind': k, 'label': lab, 'name': name, 'poly': pg, 'z': 1}
        if rid == 'All Hands on Deck': r['labelAt'] = D(1660, 665)
        rooms.append(r)
    return {'id': '2', 'label': 'Museum Floor 2', 'order': 1,
            'area': 'All Hands on Deck: A Sailor’s Life in 1812 and the Battle Theater',
            'transform': [SCALE, 0, 0], 'walkScale': WALK, 'rooms': rooms,
            'doors': [door(a, b, D(*at)) for a, b, at in MUSEUM_2_DOORS],
            'amenities': [{'type': 'stairs', 'at': STAIRS_AT}, {'type': 'elevator', 'at': ELEV_AT}],
            'labels': [{'text': 'Stairs and elevator down to the lobby floor', 'kind': 'note', 'at': D(1600, 730)}]}


def ship_floor(fid, label, order, area, spec, ladders):
    rooms, doors = deck(spec)
    return {'id': fid, 'label': label, 'order': order, 'area': area, 'transform': [SCALE, 0, 0], 'walkScale': SHIP_WALK,
            'rooms': rooms, 'doors': doors, 'amenities': [{'type': 'stairs', 'at': a} for a in ladders],
            'labels': ship_labels() + [{'text': 'Steep ladder-like steps between decks', 'kind': 'note',
                                        'at': [680, 1160]}]}


def inside(pt, pg):
    x, y = pt
    c = False
    for i in range(len(pg)):
        (x1, y1), (x2, y2) = pg[i], pg[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c


def build_floors():
    ways = osm()
    floors = [yard_floor(ways), museum_2_floor(),
              ship_floor('G', 'Ship · Gun Deck', -1, 'One deck down: the 24-pounders, the captain’s cabin '
                         'and the galley stove', GUN, [LADDER_AFT, LADDER_MAIN]),
              ship_floor('B', 'Ship · Berth Deck', -2, 'Two decks down, where the crew slept (on the '
                         'guided tour; sometimes closed)', BERTH, [LADDER_MAIN])]
    for f in floors:
        ids = [r['id'] for r in f['rooms']]
        assert len(ids) == len(set(ids)), f['id']
        for d in f['doors']: assert d['a'] in ids and d['b'] in ids, (f['id'], d)
        for a in f['amenities']:
            if not any(inside(a['at'], r['poly']) for r in f['rooms']):
                print(f'  note: {f["id"]} {a["type"]} at {a["at"]} is outside the rooms')
    return {'about': 'Built by tools/build_constitution.py. The Navy Yard is traced from OpenStreetMap (© OpenStreetMap '
                     'contributors, ODbL) on aerial imagery and turned so Pier 1 runs left to right (up is '
                     'north-east). The museum is its own 2024 visitor map, drawn about twice life size; the names '
                     'of its rooms follow the exhibits it lists in 2026. The ship is a diagram of the three decks '
                     'visitors see, drawn large. Which Pier 1 building is the Navy’s security screening is a guess.',
            'source': 'USS Constitution Museum visitor map (social narrative, 2024); OpenStreetMap; Esri World Imagery',
            'units': 'Esri World Imagery pixels at zoom 19 (about 0.22 m), turned 33.7°; the museum and the ship are '
                     'diagrams drawn larger', 'approximate': True, 'defaultFloor': '1', 'galleryWord': 'Place',
            'floors': floors}


# ---- pictures ------------------------------------------------------------------------------------------------------
def commons(name, width=1200):
    return 'https://commons.wikimedia.org/wiki/Special:FilePath/' + urllib.parse.quote(name.replace(' ', '_')) + \
        f'?width={width}'


def picture(key, src, crop=None, size=1000):
    """src: a URL (museum site or Commons). Saved as a small JPEG under data/constitution/images."""
    if not src: return None
    dest = OUT / 'images' / f'{key}.jpg'
    rel = f'data/constitution/images/{key}.jpg'
    if dest.exists(): return rel
    raw = src if isinstance(src, Path) else get(src, CACHE / 'img' / (key + '.bin'), 10 if 'ussconstitution' in src else 3)
    if not raw:
        print(f'  no picture: {src}')
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    im = Image.open(io.BytesIO(Path(raw).read_bytes()))
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA')
        bg = Image.new('RGB', im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    im = im.convert('RGB')
    if crop: im = im.crop(crop)
    im.thumbnail((size, size))
    im.save(dest, 'JPEG', quality=80 if size > 700 else 72, optimize=True, progressive=True)
    return rel


UP = SITE + '/wp-content/uploads/'
MUSEUM_CREDIT = 'USS Constitution Museum'

# (key, room, title, artist line, date, medium, text, picture URL or (Commons file,), credit, page, temporary)
ON_VIEW = [
    ('exploring-old-ironsides', 'Special Exhibition Gallery', 'Exploring Old Ironsides: New Perspectives',
     'Greg M. Cooper (photographs)', 'Opened June 9, 2026', 'Special exhibition: large-scale photographs',
     'Large photographs by Greg M. Cooper, who has photographed USS Constitution for the museum for more than 20 '
     'years: the ship underway in Boston Harbor, close details in dry dock, hidden interiors and passing weather. '
     'It opened the museum’s re-envisioned Special Exhibition Gallery, with daylight and the exposed structure of the '
     'old Navy Yard pump house. Presented by the Yawkey Foundation.',
     UP + '2026/06/Exploring-Old-Ironsides-Lnk-Image-1.png', MUSEUM_CREDIT, SITE + '/exploringoldironsides/', True),
    ('art-of-the-ship', 'Theater', 'Art of the Ship', 'Exhibition from the museum’s collection', None, 'Paintings, prints '
     'and drawings', 'In the museum’s theater: artwork of “Old Ironsides” from the museum’s collection, from dramatic '
     'scenes of life at sea to how artists have imagined, remembered and celebrated America’s Ship of State. '
     'Supported by The Boston Marine Society.', UP + '2026/06/EXP_AOS_Title_outlines.pdf-2.png', MUSEUM_CREDIT,
     SITE + '/exhibits/', True),
    ('war-and-peace', 'War and Peace Hall', '“Old Ironsides” in War and Peace', 'Core exhibit', None, None,
     'Three centuries of USS Constitution: her building in Boston and the early U.S. Navy, the highs and lows of the '
     'War of 1812, diplomatic voyages and her preservation, and how she became a national icon (look for the '
     'head of the Andrew Jackson figurehead, sawn off the ship one night in 1834). You can touch '
     'different woods, build a ship from puzzle pieces and see a model taller than you.',
     UP + '2026/06/Jackson-Gallery.png', MUSEUM_CREDIT, SITE + '/exhibits/', False),
    ('cannon-room', 'War and Peace North', 'The battle room', '“Old Ironsides” in War and Peace', None, None,
     'A room about the experience of battle in the War of 1812, with two cannons that roar when all their buttons are '
     'pushed in order (it is loud: the hall next door is quieter).', None, None,
     SITE + '/wp-content/uploads/2018/09/Social-Narrative-My-Trip-to-the-USS-Constitution-Museum-3.pdf', False),
    ('model-shop', 'Model Shop', 'The Model Shop', 'USS Constitution Model Shipwright Guild', None, None,
     'Volunteer model makers at work on miniature ships; when nobody is at the bench you can see finished models '
     'through the windows. The Guild also holds the yearly Masters of Miniature ship model show.', None, None,
     SITE + '/wp-content/uploads/2018/09/Social-Narrative-My-Trip-to-the-USS-Constitution-Museum-3.pdf', False),
    ('all-hands-on-deck', 'All Hands on Deck', 'All Hands on Deck: A Sailor’s Life in 1812', 'Core exhibit (second floor)',
     None, None, 'Join Constitution’s 1812 crew: meet real sailors and their families back home (found in decades of '
     'research in census records, diaries, letters and pension files), then scrub the deck, lie in a hammock, fire a '
     'cannon as a team and go aloft to furl a sail.', UP + '2026/06/Family-Cannon-Gallery.png', MUSEUM_CREDIT,
     SITE + '/exhibits/', False),
    ('battle-theater', 'Battle Theater', 'Battle Theater', 'All Hands on Deck', None, 'Film (captioned)',
     'A short captioned film inside All Hands on Deck that tells the story of one of Constitution’s famous battles '
     'of the War of 1812.', None, None, SITE + '/exhibits/', False),
    # the ship
    ('the-ship', 'Spar Deck Waist', 'USS Constitution, “Old Ironsides”', 'Joshua Humphreys (design); built at '
     'Edmund Hartt’s shipyard, Boston', 'Launched October 21, 1797', '44-gun frigate: live oak, white oak, pine',
     'The world’s oldest commissioned warship still afloat, crewed by active-duty U.S. Navy sailors who lead the '
     'tours. She never lost a battle; her nickname comes from 1812, when British cannonballs seemed to bounce off her '
     'thick oak sides in the fight with HMS Guerriere. Free to board (Navy security screening; photo ID for 18 and '
     'over).', ('USS Constitution Departs.jpg',), 'Wikimedia Commons',
     SITE + '/uss-constitution-facts/', False),
    ('ships-wheel', 'Quarterdeck', 'The double wheel', 'Spar deck', None, None,
     'Constitution is steered from a double wheel on the quarterdeck, so up to four sailors could hold her in a '
     'blow. Her wheel was shot away in the battle with HMS Java on December 29, 1812; the museum tells the story of the '
     'wheels that came after.', None, None, SITE + '/wp-content/uploads/dlm_uploads/2020/01/ConstitutionWheelHistory.pdf',
     False),
    ('carronades', 'Spar Deck Waist', 'The carronades', 'Spar deck', None, 'Replica 32-pounder carronades',
     'The short, heavy guns along the top deck are carronades, which threw a 32-pound ball at close range. Like every '
     'gun on board today they are 20th-century replicas.', None, None, SITE + '/uss-constitution-facts/', False),
    ('masts', 'Forecastle', 'Masts and rigging', 'Spar deck', None, None,
     'Three masts (fore, main and mizzen) and miles of rigging carry nearly an acre of sail when she is fully '
     'rigged. The mainmast stands about 220 feet above the waterline.', None, None, SITE + '/uss-constitution-facts/',
     False),
    ('gun-deck', 'Gun Deck', 'The gun deck battery', 'Gun deck', None, 'Replica 24-pounder long guns',
     'Her main battery: thirty 24-pounder long guns, fifteen on each side, each worked by a crew of about a dozen '
     'men. The guns on board today are replicas; two can fire salutes.',
     UP + '2016/07/IMG_7068-1024x755.jpg', 'Naval History & Heritage Command Detachment Boston, via the USS '
     'Constitution Museum', SITE + '/2016/07/14/decks/', False),
    ('captains-cabin', 'Captain’s Cabin', 'The captain’s cabin', 'Gun deck, at the stern', None, None,
     'The captain lived, worked and dined at the stern of the gun deck, in a great cabin lit by the stern windows, '
     'with his dining cabin and sleeping cabins beside it. Visitors look in from the door; in battle the bulkheads '
     'came down and guns stood here too.', None, None, SITE + '/2016/07/14/decks/', False),
    ('galley', 'Galley', 'The galley stove', 'Gun deck, forward', None, 'Iron stove',
     'All the crew’s food was cooked on one big iron stove forward on the gun deck: salt beef and pork, peas, '
     'biscuit and burgoo for some 450 people.', None, None, SITE + '/uss-constitution-facts/', False),
    ('berth-deck', 'Berth Deck', 'Hammocks on the berth deck', 'Berth deck', None, None,
     'The crew slept on the berth deck in hammocks slung from the beams, about 14 inches apart, and kept their few '
     'belongings in sea bags and chests. The enormous white oak knees that hold the hull together are here too.',
     UP + '2016/07/Diag-Riders-Model-1024x290.jpg', 'Naval History & Heritage Command Detachment Boston, via the USS '
     'Constitution Museum', SITE + '/2016/07/14/decks/', False),
    ('wardroom', 'Wardroom', 'The wardroom', 'Berth deck, at the stern', None, None,
     'The officers ate and spent their free time in the wardroom at the stern of the berth deck, with small '
     'staterooms on each side.', None, None, SITE + '/2016/07/14/decks/', False),
    ('cassin-young', 'USS Cassin Young', 'USS Cassin Young (DD-793)', 'National Park Service', '1943',
     'Fletcher-class destroyer', 'A World War II destroyer, hit twice by kamikazes off Okinawa in 1945, moored on the '
     'other side of Pier 1 and shown by the National Park Service (check the Park Service for days and hours).',
     None, None, 'https://www.nps.gov/bost/learn/historyculture/usscassinyoung.htm', False),
    ('navy-yard-visitor-center', 'Visitor Center', 'Charlestown Navy Yard Visitor Center', 'National Park Service',
     None, None, 'The Park Service’s visitor center in Building 5: rangers, exhibits on the Navy Yard’s 174 years, '
     'restrooms, and the way to Pier 1.', None, None, 'https://www.nps.gov/bost/planyourvisit/cny.htm', False),
]

WHERE = {
    'Special Exhibition Gallery': 'Which gallery the show is in is a guess (the museum’s map of 2024 calls this room '
                                  'Today’s Navy).',
    'Gun Deck': 'One deck below the top deck: down the steep ladder.',
    'Captain’s Cabin': 'At the stern of the gun deck.',
    'Galley': 'Forward on the gun deck.',
    'Berth Deck': 'Two decks down; on the guided tour, sometimes closed.',
    'Wardroom': 'Two decks down, at the stern; on the guided tour, sometimes closed.',
}


def build_works(floors):
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    works = []
    for key, room, title, artist, date, medium, text, pic, credit, url, temp in ON_VIEW:
        fl, gname = rooms[room]
        src = commons(pic[0]) if isinstance(pic, tuple) else pic
        img = picture(f'ussc-{key}', src)
        a = {'id': f'ussc-{key}', 'title': title, 'artist': artist, 'date': date, 'medium': medium,
             'description': text, 'descriptionKind': 'From the museum’s descriptions', 'gallery': room,
             'galleryName': gname, 'floor': fl, 'placeNote': WHERE.get(room), 'url': url, 'image': img,
             'imageCredit': credit if img else None}
        if temp: a['temporary'] = True
        works.append({k: v for k, v in a.items() if v not in (None, '', [])})
    return {'source': 'USS Constitution Museum website (ussconstitutionmuseum.org)', 'checked': CHECKED,
            'count': len(works), 'complete': False, 'artworks': works}


def year(s):
    m = re.search(r'(1[5-9]\d\d|20\d\d)', s or '')
    return int(m.group(1)) if m else None


def build_guide(works):
    rows = []
    for a in works['artworks']:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a['artist'], 'date': a.get('date'),
                     'medium': a.get('medium'), 'url': a['url'], 'imageUrl': a.get('image'), 'onView': True,
                     'gallery': a['gallery'], 'floor': a['floor']}.items() if v not in (None, '')})
    coll = CACHE / 'collection.json'
    n = 0
    if coll.exists():
        for it in json.loads(coll.read_text()):
            if not it.get('title'): continue
            img = None
            if it.get('picture'):
                img = picture('ussc-c-' + it['slug'][:60], ROOT / it['picture'], size=600)
            rows.append({k: v for k, v in {
                'id': 'ussc-c-' + it['slug'][:60], 'title': it['title'], 'artist': it.get('Creator'),
                'date': it.get('Date Created'), 'year': year(it.get('Date Created')), 'medium': it.get('Medium'),
                'url': it['url'], 'imageUrl': img, 'onView': False}.items() if v not in (None, '')})
            n += 1
    print(f'  collection: {n} objects')
    return {'museum': MUSEUM, 'name': NAME, 'checked': CHECKED,
            'source': 'USS Constitution Museum: exhibits, visitor guides and online collection (ussconstitutionmuseum.org)',
            'onViewKnown': True, 'imageCredit': 'USS Constitution Museum (collection pictures CC BY-NC-ND 3.0)',
            'note': 'The exhibits and the ship’s decks come first: they are what you see today. After them comes the '
                    'museum’s online collection; the museum does not say which of those objects are on view.',
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
    print(f'{works["count"]} on view ({sum("image" in a for a in works["artworks"])} with pictures); museum page '
          f'{len(guide["works"])} ({sum(bool(w.get("imageUrl")) for w in guide["works"])} pictures)')


if __name__ == '__main__':
    sys.exit(main())
