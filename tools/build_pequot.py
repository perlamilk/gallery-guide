#!/usr/bin/env python3
"""Build the Mashantucket Pequot Museum & Research Center map guide (run: python3 tools/build_pequot.py).

    data/pequot/floors.json       Levels 1, 2 and 3, seen from above (flat 2D)
    data/pequot/artworks.json     the permanent exhibits, in the order of the museum's own guide
    data/pequot/images/           their pictures, made smaller for phones
    data/guides/Q6783079.json     the same list for the museum page, plus collection objects not known to be on view

Where the information comes from
--------------------------------
The map is the museum's own "Museum Property Guide Map" (July 2023, printed for visitors; a PDF under
pequotmuseum.org/wp-content/uploads, cached in .cache/pequot). Page 1 draws the three levels, each in its own colour,
with the Gathering Space, front desk, coats, ATM, shop, libraries, restrooms, elevators, escalators, emergency exits,
both entrances and the exhibit route numbered 1-15. Levels 1 and 2 are traced from its walls by
tools/trace_pequot.py (tools/data/pequot-trace.json); Level 3, which has few inner walls, is drawn here by hand from
the same page. Coordinates are pixels of the page at 110 dpi. The three levels are drawn separately on the page, so
each is moved (OFFSET) to sit over the others; the offsets line up the elevator by the Level 2 exhibit exit, which the
map draws on all three levels, and the two escalators between Levels 1 and 2.

The exhibits: the 26 numbered exhibits of the museum's 2022 "Journey Through Time" guide map (same PDF folder) and
the 15 stops of the 2023 guide, which moved a few exhibits (World of Ice and the Arrival of the People are on Level 1
in 2023, on Level 2 in 2022: the newer guide wins). Their pictures are the photos printed in the 2023 guide, one per
stop. pequotmuseum.org answers 403 to cloud machines (Cloudflare), so the pages can't be read; its PDFs can. Objects
from the collection come from the museum's Google Arts & Culture pages (tools/harvest_pequot.py); none is known to be
on view, so they are listed on the museum page only. Where the line between two exhibits is not a wall on the map,
the room each is in is the map's own number placement.
"""
import io
import json
import re
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'pequot'
CACHE = ROOT / '.cache' / 'pequot'
MUSEUM = 'Q6783079'
NAME = 'Mashantucket Pequot Museum & Research Center'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
SITE = 'https://www.pequotmuseum.org'
GUIDE_2023 = SITE + '/wp-content/uploads/FOX_100075-1_Jul2023_MuseumProperty_GuideMap_8-5x14-1.pdf'
GUIDE_2022 = SITE + '/wp-content/uploads/WEB-FOX_86645-1_MPMRC_2022_GuideMap.pdf'
GUIDE_CREDIT = 'Mashantucket Pequot Museum & Research Center (museum guide map, 2023)'
GAC_CREDIT = 'Mashantucket Pequot Museum & Research Center, via Google Arts & Culture'
OFFSET = {'3': (0, 0), '2': (0, -476), '1': (125, -869)}
S = 0.3            # transform: map pixels x2 -> frame; about 0.21 m per map pixel


def P(lv, q):
    dx, dy = OFFSET[lv]
    return [round((q[0] + dx) * 2, 1), round((q[1] + dy) * 2, 1)]


def arc(cx, cy, r, a0, a1, n=24):
    import math
    return [(round(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), 1),
             round(cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n)), 1)) for i in range(n + 1)]


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# ---- Level 3 (entry floor), by hand --------------------------------------------------------------------------------
# The Gathering Space is a glass drum: its outer wall is a circle of radius 115 around (652.5, 495).
GATHER = arc(652.5, 495, 115, 28, -171, 32) + [(550, 497), (580, 530), (600, 543), (640, 550), (648, 560), (648, 602),
                                                 (765, 602), (765, 592), (802, 597), (807, 580)]
RESTROOMS_3 = rect(380, 505, 427, 575)
L3 = [
    ('Gathering Space', 'space', 'The Gathering Space', GATHER, None),
    ('Museum Shop', 'space', 'Museum Gift Shop', [(507, 535), (580, 530), (600, 543), (640, 550), (648, 560), (648, 595),
                                                  (507, 595)], None),
    ('Hallway 3', 'corridor', 'Hallway',
     [(377, 454), (538, 477), (550, 497), (580, 530), (507, 535), (507, 593), (377, 593)], None),
    ('Restrooms 3', 'space', 'Restrooms', RESTROOMS_3, None),
    ('Group Entrance', 'corridor', 'Group entrance', [(358, 451), (377, 454), (377, 593), (358, 593)], None),
    ('Research Library', 'space', 'Research Library',
     [(257, 437), (358, 451), (358, 565), (272, 565), (272, 595), (120, 595), (120, 505), (252, 505), (252, 490),
      (249, 487)], None),
    ("Children's Library", 'space', 'Children’s Library',
     [(272, 565), (358, 565), (358, 593), (345, 593), (345, 602), (320, 622), (250, 630), (222, 630), (222, 595),
      (272, 595)], None),
]
L3_HOLES = {'Hallway 3': [RESTROOMS_3]}
L3_DOORS = [('Gathering Space', 'Museum Shop', (620, 547)), ('Gathering Space', 'Hallway 3', (565, 513)),
            ('Hallway 3', 'Museum Shop', (507, 560)), ('Hallway 3', 'Restrooms 3', (404, 505)),
            ('Hallway 3', 'Group Entrance', (377, 520)), ('Group Entrance', 'Research Library', (358, 520)),
            ('Group Entrance', "Children's Library", (358, 580))]
L3_AMEN = [('entrance', 745, 597), ('entrance', 368, 590), ('info', 708, 565), ('coat', 680, 585),
           ('restroom', 404, 540), ('shop', 560, 570), ('elevator', 560, 447), ('elevator', 662, 551),
           ('elevator', 782, 586), ('stairs', 585, 459)]
L3_LABELS = [('Terrace', 300, 425), ('Terrace', 790, 425), ('MAIN ENTRANCE ↓', 745, 622), ('GROUP ENTRANCE ↓', 368, 622),
             ('Observation Tower ↗', 812, 562)]
L3_NOTES = [('Ramp down to the exhibits', 640, 418), ('Front desk', 708, 556), ('Coats', 682, 578), ('ATM', 652, 575),
            ('Café (Level 4): closed for now', 470, 470)]

# ---- Levels 1 and 2, from tools/trace_pequot.py -------------------------------------------------------------------
# traced name -> (id, kind, name shown, short label)
L2_ROOMS = {
    'Exhibit Entrance': ('Exhibit Entrance', 'gallery', 'Exhibit Entrance: the introduction, a scale model of the '
                         'reservation and tribal life today', 'Entrance'),
    'The Glacier': ('The Glacier', 'gallery', 'The Glacier: the escalator down through a glacial crevasse to Level 1',
                    'Glacier'),
    'Ramp to Level 3': ('Ramp to Level 3', 'corridor', 'Ramp between Level 2 and Level 3 (the Gathering Space)', None),
    'Ramp Lobby': ('Ramp Lobby', 'corridor', 'Lobby at the bottom of the ramp: the way back up to the Gathering Space',
                   None),
    'Auditorium': ('Auditorium', 'space', 'Auditorium', None),
    'Auditorium Lobby': ('Auditorium Lobby', 'corridor', 'Auditorium lobby and restrooms', None),
    'Mashantucket Gallery': ('Mashantucket Gallery', 'gallery', 'Mashantucket Gallery: changing exhibitions of Native '
                             'art and culture', 'Mashantucket Gallery'),
    'Lower Hall': ('Hallway 2', 'corridor', 'Hallway', None),
    'Village Overlook': ('Village Overlook', 'corridor', 'Village Overlook: look down into the Pequot Village below',
                         None),
    'Escalator Hall': ('Escalator Hall 2', 'corridor', 'Escalator and elevator from Level 1', None),
    'Life on the Reservation': ('Life on the Reservation', 'gallery', 'Life on the Reservation: Robin Cassacinamon, '
                                'the Fort at Mashantucket, and the door out to the 1780 Farmstead', 'Reservation'),
    'The Changing Reservation': ('The Changing Reservation', 'gallery', 'The Changing Reservation', 'Changing'),
    'Tribal Portrait Gallery': ('Tribal Portrait Gallery', 'gallery', 'Tribal Portrait Gallery', 'Portraits'),
    'Meeting House Mini-Theater': ('Meeting House Mini-Theater', 'gallery', 'Meeting House Mini-Theater',
                                   'Meeting House'),
    'Federal Recognition Theater': ('Federal Recognition Theater', 'gallery', 'Federal Recognition Theater and the '
                                    'galleries around the two round exhibit rooms (where the theater is exactly is '
                                    'approximate)', 'Recognition'),
}
L2_CLOSED = ['Fort Theater', 'Recognition Theater', 'Overlook Case']
L2_DOORS = [('The Glacier', 'Exhibit Entrance'), ('Ramp to Level 3', 'Exhibit Entrance'),
            ('Ramp to Level 3', 'Ramp Lobby'), ('Exhibit Entrance', 'Ramp Lobby'), ('Auditorium', 'Ramp Lobby'),
            ('Auditorium Lobby', 'Ramp Lobby'), ('Auditorium Lobby', 'Lower Hall'), ('Mashantucket Gallery', 'Lower Hall'),
            ('Lower Hall', 'Tribal Portrait Gallery'), ('The Changing Reservation', 'Tribal Portrait Gallery'),
            ('The Changing Reservation', 'Meeting House Mini-Theater'),
            ('Life on the Reservation', 'Meeting House Mini-Theater'), ('Escalator Hall', 'Life on the Reservation'),
            ('Village Overlook', 'Escalator Hall'), ('Lower Hall', 'Village Overlook'),
            ('Life on the Reservation', 'Federal Recognition Theater'),
            ('Tribal Portrait Gallery', 'Federal Recognition Theater'), ('Lower Hall', 'Federal Recognition Theater')]
L2_AMEN = [('stairs', 585, 935), ('elevator', 572, 926), ('stairs', 770, 932), ('elevator', 790, 962),
           ('restroom', 547, 990), ('stairs', 409, 826), ('elevator', 439, 802)]
L2_LABELS = [('1780 Farmstead (outside) ↖', 282, 790)]
L2_NOTES = [('Escalator to Level 1', 770, 945), ('Escalator from Level 1', 409, 838), ('Ramp up to Level 3', 588, 952)]

L1_ROOMS = {
    'Life in a Cold Climate': ('Life in a Cold Climate', 'gallery', 'Life in a Cold Climate: Ice Age animals and the '
                               'caribou hunt', 'Cold Climate'),
    'World of Ice': ('World of Ice', 'gallery', 'World of Ice and the Arrival of the People; the escalator from Level 2 '
                     'arrives here', 'World of Ice'),
    'Tool Theater': ('Tool Theater', 'gallery', 'Tool Theater', 'Tools'),
    'Four Seasons': ('Four Seasons', 'gallery', 'The Four Seasons and the Three Sisters; pick up the audio tour here',
                     'Four Seasons'),
    'Pequot Daily Life Gallery': ('Pequot Daily Life Gallery', 'gallery', 'Pequot Daily Life Gallery (a side gallery '
                                  'of the village)', 'Daily Life'),
    'Pequot Village': ('Pequot Village', 'gallery', '16th-Century Pequot Village', 'Pequot Village'),
    'Palisaded Fort': ('Palisaded Fort', 'gallery', 'Palisaded fort and the way out of the village: the Arrival of the '
                       'Europeans', 'Fort'),
    'Pequot Society Gallery': ('Pequot Society Gallery', 'gallery', 'Pequot Society Gallery (a side gallery of the '
                               'village)', 'Society'),
    'Clash of Cultures': ('Clash of Cultures', 'gallery', 'Clash of Cultures: the Pequot War of 1636-1637',
                          'Pequot War'),
    'War Theater 1': ('War Theater 1', 'gallery', 'War Theater 1 and the escalator up to Level 2', 'War Theater 1'),
    'War Theater 2': ('War Theater 2', 'gallery', 'War Theater 2: The Witness (film)', 'War Theater 2'),
    'South Hall': ('South Hall', 'corridor', 'Hallway to the elevator', None),
}
L1_DOORS = [('Life in a Cold Climate', 'World of Ice'), ('World of Ice', 'Four Seasons'), ('Tool Theater', 'Four Seasons'),
            ('Four Seasons', 'Pequot Daily Life Gallery'), ('Pequot Village', 'Pequot Daily Life Gallery'),
            ('Pequot Village', 'Palisaded Fort'), ('Pequot Village', 'Pequot Society Gallery'),
            ('Pequot Daily Life Gallery', 'Pequot Society Gallery'), ('Pequot Daily Life Gallery', 'South Hall'),
            ('Tool Theater', 'South Hall'), ('Palisaded Fort', 'Clash of Cultures'),
            ('Clash of Cultures', 'War Theater 1'), ('War Theater 1', 'War Theater 2')]
L1_AMEN = [('stairs', 690, 1335), ('stairs', 265, 1210), ('elevator', 440, 1315), ('elevator', 252, 1184),
           ('restroom', 152, 1294)]
L1_LABELS = []
L1_NOTES = [('Audio tour pickup', 622, 1180), ('Escalator from Level 2', 690, 1347), ('Escalator to Level 2', 268, 1222)]


# label points where the seed sits awkwardly for a label
LABEL_AT = {'Federal Recognition Theater': (300, 925), 'Four Seasons': (682, 1218), 'Pequot Daily Life Gallery': (560, 1228), 'War Theater 1': (225, 1250), 'Clash of Cultures': (175, 1215)}


def inside(pt, poly):
    x, y = pt
    c = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c


def area(poly):
    return abs(sum(poly[i - 1][0] * poly[i][1] - poly[i][0] * poly[i - 1][1] for i in range(len(poly)))) / 2


def traced_floor(lv, trace, rooms_map, closed_names, door_pairs):
    t = trace[lv]
    rooms, closed = [], []
    for name, poly in t['polys'].items():
        if name in closed_names:
            closed.append({'poly': [P(lv, q) for q in poly]})
            continue
        rid, kind, shown, short = rooms_map[name]
        r = {'id': rid, 'kind': kind, 'name': shown, 'poly': [P(lv, q) for q in poly]}
        if kind == 'gallery': r['label'] = short
        if name in LABEL_AT or kind != 'corridor':
            r['labelAt'] = P(lv, LABEL_AT.get(name) or t['seeds'][name])      # where the map writes its name
        rooms.append(r)
    at = {tuple(sorted((a, b))): (x, y) for a, b, x, y, n in t['doors']}
    doors = []
    for a, b in door_pairs:
        k = tuple(sorted((a, b)))
        if k not in at: raise SystemExit(f'Level {lv}: no doorway traced between {a} and {b}')
        doors.append({'a': rooms_map[a][0], 'b': rooms_map[b][0], 'at': P(lv, at[k]), 'width': 16, 'axis': 'o'})
    return rooms, closed, doors


def floor(lv, label, order, area_text, rooms, closed, doors, amen, labels, notes):
    f = {'id': lv, 'label': label, 'order': order, 'transform': [S, 0, 0], 'area': area_text, 'rooms': rooms,
         'closed': closed,
         'amenities': [{'type': t, 'at': P(lv, (x, y))} for t, x, y in amen],
         'labels': [{'text': t, 'kind': 'area', 'at': P(lv, (x, y))} for t, x, y in labels],
         'notes': [{'text': t, 'kind': 'note', 'at': P(lv, (x, y))} for t, x, y in notes],
         'doors': doors}
    ids = [r['id'] for r in rooms]
    assert len(ids) == len(set(ids)), lv
    for a in f['amenities']:
        if not any(inside(a['at'], r['poly']) for r in rooms):
            print(f'  note: Level {lv} {a["type"]} at {a["at"]} is on a wall line (routes use the nearest room)')
    return f


def build_floors():
    trace = json.loads((ROOT / 'tools' / 'data' / 'pequot-trace.json').read_text())
    l3_rooms = []
    for rid, kind, name, poly, short in L3:
        r = {'id': rid, 'kind': kind, 'name': name, 'poly': [P('3', q) for q in poly]}
        if rid in L3_HOLES: r['holes'] = [[P('3', q) for q in h] for h in L3_HOLES[rid]]
        l3_rooms.append(r)
    l3_doors = [{'a': a, 'b': b, 'at': P('3', p), 'width': 16, 'axis': 'o'} for a, b, p in L3_DOORS]
    r2, c2, d2 = traced_floor('2', trace, L2_ROOMS, L2_CLOSED, L2_DOORS)
    r1, c1, d1 = traced_floor('1', trace, L1_ROOMS, [], L1_DOORS)
    floors = [
        floor('1', 'Level 1', 0, 'World of Ice · Life in a Cold Climate · caribou hunt · Four Seasons · Pequot Village · '
              'Clash of Cultures · The Witness', r1, c1, d1, L1_AMEN, L1_LABELS, L1_NOTES),
        floor('2', 'Level 2', 1, 'Exhibit entrance · The Glacier · Life on the Reservation · 1780 Farmstead · Tribal '
              'Portrait Gallery · Mashantucket Gallery · auditorium', r2, c2, d2, L2_AMEN, L2_LABELS, L2_NOTES),
        floor('3', 'Level 3', 2, 'Entry floor: Gathering Space, front desk, shop, libraries, observation tower',
              l3_rooms, [], l3_doors, L3_AMEN, L3_LABELS, L3_NOTES),
    ]
    return {'about': 'Built by tools/build_pequot.py. Traced from the Mashantucket Pequot Museum’s own guide map (July '
                     '2023): the three levels, the Gathering Space, front desk, coats, shop, libraries, restrooms, '
                     'elevators, escalators, the ramp, both entrances and every exhibit area where the map puts them. '
                     'Walls are simplified; where the map draws no wall between two exhibits, the line between them '
                     'is a guess. The café on Level 4 is not drawn (it is closed for now).',
            'source': 'Mashantucket Pequot Museum & Research Center, Museum Property Guide Map (July 2023)',
            'units': 'pixels of the museum’s guide map page (110 dpi) x 2, each level moved to sit over the others',
            'approximate': False, 'defaultFloor': '3', 'galleryWord': 'Gallery', 'floors': floors}


# ---- pictures ------------------------------------------------------------------------------------------------------

def guide_photos():
    """The 2023 guide prints one photo per stop; pdfimages numbers them in page order (a-004 ... a-019)."""
    pdf = CACHE / 'FOX_100075-1_Jul2023_MuseumProperty_GuideMap_8-5x14-1.pdf'
    if not pdf.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        subprocess.run(['curl', '-s', '-f', '-L', '-A', UA, '-o', str(pdf), GUIDE_2023], check=True)
    d = CACHE / 'pdfimg'
    if not (d / 'a-004.jpg').exists():
        d.mkdir(exist_ok=True)
        subprocess.run(['pdfimages', '-j', str(pdf), str(d / 'a')], check=True)
    return d


def picture(key, src):
    """src: a local file (Path) or a URL."""
    if not src: return None
    if isinstance(src, Path):
        data = src.read_bytes()
    else:
        raw = CACHE / 'img' / (key + '.bin')
        if not raw.exists():
            raw.parent.mkdir(parents=True, exist_ok=True)
            out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '90', '-A', UA, src], capture_output=True).stdout
            time.sleep(1.5)
            if not out:
                print(f'  no picture: {src}')
                return None
            raw.write_bytes(out)
        data = raw.read_bytes()
    dest = OUT / 'images' / f'{key}.jpg'
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        im = Image.open(io.BytesIO(data)).convert('RGB')
        im.thumbnail((1000, 1000))
        im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)
    return f'data/pequot/images/{key}.jpg'


def gac_rows():
    p = CACHE / 'gac-works.json'
    if not p.exists(): raise SystemExit('run tools/harvest_pequot.py first')
    rows, seen = [], set()
    for r in json.loads(p.read_text()):
        if (r['title'], r['date']) in seen: continue
        seen.add((r['title'], r['date']))
        rows.append(r)
    return rows


def gac_big(url):
    # Google Arts & Culture pictures take a size after '='
    return re.sub(r'=[^/]*$', '', url) + '=w1000' if url else None


# ---- the exhibits ---------------------------------------------------------------------------------------------------
# (key, room, title, kind, text, picture: guide photo number or 'gac:<title>', the museum's guide numbers, note)
G23 = 'Stop {} of the museum’s 2023 guide map.'
EXHIBITS = [
    # Level 3
    ('gathering-space', 'Gathering Space', 'The Gathering Space', 'Gallery',
     'Begin your tour on the entry floor (Level 3), in the Gathering Space, near the gift shop. The tall hall is walled '
     'in glass.', 4, '1', None),
    ('ramp', 'Gathering Space', 'The ramp to the exhibits', 'Gallery',
     'Take the ramp or the elevator on the far side of the Gathering Space to start your exhibit tour on Level 2. The '
     'exhibits run as a timeline, from 18,000 years ago to the present day.', 16, '2', None),
    ('observation-tower', 'Gathering Space', 'Observation Tower', 'Place',
     'Don’t forget to visit the observation tower! Its elevator is by the main entrance.', 19, None, None),
    ('museum-shop', 'Museum Shop', 'Museum Gift Shop', 'Shop',
     'From Pendleton blankets, pottery and craft supplies to handmade birch baskets, jewelry, textiles and locally '
     'harvested maple syrup: the shop sells work made by certified Native American artists.', None, None, None),
    # Level 2: the way in
    ('entrance', 'Exhibit Entrance', 'Introduction', 'Exhibit',
     'At the bottom of the ramp, turn left into the exhibits. A large colour photo of today’s tribal members and an '
     'interactive, glass-enclosed tabletop model of the reservation introduce Pequot life from centuries past to the '
     'present.', 18, '3 (2023) · 1 (2022)', None),
    ('glacier', 'The Glacier', 'The Glacier', 'Exhibit',
     'Travel through a glacial crevasse in New England during the Ice Age. The escalator takes you down to Level 1.',
     None, '2 (2022)', None),
    # Level 1: Life in a Cold Climate
    ('world-of-ice', 'World of Ice', 'The World of Ice', 'Exhibit',
     'The centrepiece of this exhibit is a revolving globe showing the advance and retreat of the Wisconsin Glacier.',
     14, '4 (2023) · 3 (2022)', 'The 2023 guide puts the World of Ice on Level 1, by the escalator from Level 2 (the '
     '2022 guide had it on Level 2).'),
    ('arrival-of-the-people', 'World of Ice', 'Arrival of the People Gallery', 'Exhibit',
     'The works of nine Native artists represent the creation stories of each artist’s tribe.', None,
     '4 (2023) · 4 (2022)', 'The 2023 guide puts the Native art and creation stories with the World of Ice on Level 1.'),
    ('arrival-of-the-people-theater', 'World of Ice', 'Arrival of the People Theater', 'Film',
     'Storytellers relate creation stories in English and in their own languages (a short film).', None,
     '4 (2023) · 5 (2022)', 'The 2023 guide puts the storytellers’ film with the World of Ice on Level 1.'),
    ('cold-climate', 'Life in a Cold Climate', 'Life in a Cold Climate', 'Exhibit',
     'Exhibits on large animals that once roamed New England, like the mastodon, the giant beaver and dire wolves.',
     17, '5', None),
    ('caribou-hunt', 'Life in a Cold Climate', 'Caribou Hunt Diorama', 'Diorama',
     'A life-size re-creation of a caribou hunt 11,000 years ago: discover how family members took part.', 5,
     '6 (2023) · 6 (2022)', None),
    ('changing-environment', 'World of Ice', 'The Changing Environment', 'Diorama',
     'A life-size diorama and touch-screen computers detail the forest habitat of Connecticut, and show how '
     'scientists learned how this area changed over the past 15,000 years.', 15, '7', None),
    ('four-seasons', 'Four Seasons', 'The Four Seasons', 'Diorama',
     'Dioramas portray life at Mashantucket from 8,000 to 3,000 years ago, season by season, with ancient tools.',
     6, '8', None),
    ('tool-theater', 'Tool Theater', 'Tool Theater', 'Film',
     'A short film on making and using stone tools: the actual tools used by the Mashantucket Pequots for farming and '
     'building.', None, '8 (2023) · 9 (2022)', None),
    ('three-sisters', 'Four Seasons', 'Introduction to Horticulture: the Three Sisters', 'Diorama',
     'A life-size diorama of growing corn, beans and squash, which Natives call the “Three Sisters”. Pick up an '
     'audio guide here before you enter the village, and dial the numbers on the floor to hear each scene explained.',
     8, '9 (2023) · 10, 11 (2022)', None),
    # Level 1: The Pequot Village
    ('pequot-village', 'Pequot Village', '16th-Century Pequot Village', 'Diorama',
     'Walk through a life-size Pequot village and imagine life before the arrival of Europeans: a realistic coastal '
     'and woodland setting of the 1500s, with wigwams, people at work and the sounds of the village.',
     'gac:Gallery View in the Pequot Village', '10 (2023) · 12 (2022)', None),
    ('daily-life', 'Pequot Daily Life Gallery', 'Pequot Daily Life Gallery', 'Gallery',
     'Once in the village, notice the side galleries: videos of Native artisans making the tools and utensils of '
     'everyday life in southeastern Connecticut 450 years ago.', 7, '10 (2023) · 13 (2022)', None),
    ('society', 'Pequot Society Gallery', 'Pequot Society Gallery', 'Gallery',
     'Learn about the Tribe’s social and political organization, ceremonies, spirituality and medicine.', None,
     '14 (2022)', None),
    ('arrival-of-europeans', 'Palisaded Fort', 'Arrival of the Europeans Gallery', 'Gallery',
     'The political, economic and religious reasons that led to the arrival of the English and the Dutch.', None,
     '15 (2022)', 'Where the 2022 guide puts it, on the way out of the village (approximate).'),
    ('palisaded-fort', 'Palisaded Fort', 'Palisaded Fort', 'Diorama',
     'A ring of tall posts around part of the village: the kind of fort the Pequots built in the 1600s.', None, None,
     None),
    # Level 1: The Pequot War
    ('prelude-to-war', 'Clash of Cultures', 'Prelude to War', 'Exhibit',
     'Leaving the village, enter the Clash of Cultures exhibits: video displays tell how trading conflicts led to '
     'tension between the Pequots, the English and the Dutch.', None, '11 (2023) · 16 (2022)', None),
    ('wampum-theater', 'Clash of Cultures', 'Wampum Theater', 'Film',
     'Learn about the tube-shell beads first used for ceremonial purposes and then for trade.', None, '17 (2022)',
     'Next to War Theater 1 in the 2022 guide.'),
    ('massacre-at-mystic', 'Clash of Cultures', 'The Massacre at Mystic', 'Exhibit',
     'How, in 1637, the colonies of Connecticut and Massachusetts attacked the fort at Mystic, killing about 600 '
     'Pequots.', None, '18 (2022)', None),
    ('the-witness', 'War Theater 2', 'The Witness', 'Film',
     'A dramatic half-hour film about the 1637 Pequot War, seen through the eyes of a Pequot elder who survived the '
     'Massacre at Mystic (for ages 12 and older). Viewings at 11 AM, 1 PM and 3 PM.', 9, '11 (2023) · 19 (2022)',
     'The 2023 guide map points The Witness to War Theaters 1 and 2.'),
    # Level 2: Then back to the present
    ('life-on-the-reservation', 'Life on the Reservation', 'Life on the Reservation', 'Exhibit',
     'Take the escalator to Level 2, and discover what life on and off the reservation meant for Pequot families.',
     10, '12', None),
    ('robin-cassacinamon', 'Life on the Reservation', 'Robin Cassacinamon', 'Exhibit',
     'Meet the Pequot sachem (1645–1692) who helped the Pequots return to their land.', None, '20 (2022)', None),
    ('fort-at-mashantucket', 'Life on the Reservation', 'Explore the Fort at Mashantucket', 'Interactive',
     'An interactive program to move through a 3D computer model of the fort that archaeologists discovered on this '
     'site in 1992.', None, '21 (2022)', None),
    ('farmstead', 'Life on the Reservation', '1780 Farmstead', 'Exhibit',
     'Step inside a typical farmstead. In warm weather, tour the two-acre garden outside (the door at the top of the '
     'map).', None, '22 (2022)', None),
    ('meeting-house', 'Meeting House Mini-Theater', 'Meeting House Mini-Theater: Our Remembered Sisters', 'Film',
     'Our Remembered Sisters describes the lives of three Mashantucket women in the first half of the 19th century.',
     None, '23 (2022)', None),
    ('changing-reservation', 'The Changing Reservation', 'The Changing Reservation', 'Interactive',
     'A computer interactive shows how the shape and nature of Pequot land changed over the last 300 years.', None,
     '24 (2022)', None),
    ('federal-recognition', 'Federal Recognition Theater', 'Federal Recognition Theater: Bringing The People Home',
     'Film', 'The film Bringing The People Home tells how the Tribe achieved federal recognition in 1983.', None,
     '25 (2022)', 'Approximate: between the two round exhibit rooms, where the 2022 guide puts it.'),
    ('portrait-gallery', 'Tribal Portrait Gallery', 'Tribal Portrait Gallery', 'Gallery',
     'Photos of present-day members of the Mashantucket Pequot Tribal Nation; listen to their voices as they recount '
     'what it means to be a Pequot and Native American.', 11, '13 (2023) · 26 (2022)', None),
    ('mashantucket-gallery', 'Mashantucket Gallery', 'Mashantucket Gallery', 'Exhibition',
     'Exit the Portrait Gallery and walk straight ahead to the Mashantucket Gallery, where changing exhibitions '
     'highlight Native art and culture. Then turn right, go through the double doors, cross the auditorium lobby and '
     'take the ramp back up to the Gathering Space.', 12, '14, 15', None),
]

# Collection objects on Google Arts & Culture that are not museum objects (book plates of other libraries, news
# clippings, videos, photos of events, maps drawn for a story)
GAC_SKIP = re.compile(r'John Carter Brown|^Watch ', re.I)
GAC_SKIP_TITLES = {'Summer Campers to Search Pond for Indian Relics', 'Old Indian Dugout Canoe Found',
                   'Drought Uncovers Important Artifact', '300-Year-Old Indian Canoe is Discovered',
                   'The Making of the Mission Mishoon', 'The Making of the Mishoon!', 'Gallery View in the Pequot Village',
                   'Gallery View in the Gathering Space', 'Battlefield Map', 'Map of Reduced Mashantucket',
                   'Map of Pequot Traditional Territory', 'Traditional Territory of the Pequots', 'Map of Nameag',
                   'Map of Noank', 'Map of Noank and Mashantucket', 'The Many Rolls of Dolls', 'Dene Doll Family',
                   'Underhill Engraving'}
STORY = {'Neetôpáwees': 'Neetôpáwees (dolls)', 'Battlefields of the Pequot War': 'Battlefields of the Pequot War',
         'Reclaiming the Waterways': 'Reclaiming the Waterways'}


def year_of(date):
    m = re.search(r'(\d{4})', date or '')
    return int(m[1]) if m else None


def nice_date(d):
    if not d: return None
    m = re.fullmatch(r'(\d{4})/(\d{4})', d)
    if m: return m[1] if m[1] == m[2] else f'{m[1]}–{m[2]}'
    m = re.fullmatch(r'(\d{4})-\d\d-\d\d', d)
    return m[1] if m else d


def build_works(floors):
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    photos = guide_photos()
    gac = {r['title']: r for r in gac_rows()}
    works = []
    for key, room, title, kind, text, pic, nums, note in EXHIBITS:
        fl, gname = rooms[room]
        if isinstance(pic, int):
            img, credit = picture(f'pequot-{key}', photos / f'a-{pic:03d}.jpg'), GUIDE_CREDIT
        elif pic:
            img, credit = picture(f'pequot-{key}', gac_big(gac[pic[4:]]['image'])), GAC_CREDIT
        else:
            img, credit = None, None
        where = (f'Number {nums} on the museum’s guide maps. ' if nums else '') + (note or '')
        a = {'id': f'pequot-{key}', 'title': title, 'artist': kind, 'description': text, 'gallery': room,
             'galleryName': gname, 'floor': fl, 'placeNote': where.strip() or 'Where the museum’s guide map puts it.',
             'url': GUIDE_2023, 'image': img, 'imageCredit': credit if img else None}
        if room == 'Mashantucket Gallery': a['temporary'] = True
        works.append({k: v for k, v in a.items() if v not in (None, '', [])})
    return {'source': 'Mashantucket Pequot Museum & Research Center: guide maps (2023 and 2022)',
            'checked': time.strftime('%Y-%m-%d'), 'count': len(works), 'complete': False, 'artworks': works}


def build_guide(works):
    rows = []
    for a in works['artworks']:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a['artist'], 'url': a['url'],
                     'imageUrl': a.get('image'), 'onView': True, 'gallery': a['gallery'],
                     'floor': a['floor']}.items() if v not in (None, '')})
    n = 0
    for r in gac_rows():
        if r['title'] in GAC_SKIP_TITLES or GAC_SKIP.search(r['text'] or '') or not r['image']: continue
        if 'Video' in r['title'] or 'Powwow' in r['title']: continue
        n += 1
        key = 'pequot-gac-' + re.sub(r'[^a-z0-9]+', '-', (r['title'] + ' ' + (r['date'] or '')).lower()).strip('-')[:60]
        maker = r['artist'] or (r['credit'] if r['credit'] and not r['credit'].startswith(('Gift', 'On loan', 'Chief',
                                                                                         'Mashantucket'))
                                else None)
        rows.append({k: v for k, v in {
            'id': key, 'title': r['title'], 'artist': maker or 'Unknown maker', 'date': nice_date(r['date']),
            'year': year_of(r['date']), 'medium': r['medium'] or None,
            'credit': r['credit'] if r['credit'].startswith(('Gift', 'On loan')) else None,
            'exhibition': STORY.get(r['story']), 'url': r['gac'], 'imageUrl': picture(key, gac_big(r['image'])),
            'onView': False}.items() if v not in (None, '')})
    print(f'  {n} collection objects from Google Arts & Culture')
    return {'museum': MUSEUM, 'name': NAME, 'checked': time.strftime('%Y-%m-%d'),
            'source': 'Mashantucket Pequot Museum & Research Center: guide maps (2023, 2022) and its Google Arts & '
                      'Culture pages', 'onViewKnown': True,
            'note': 'The museum’s permanent exhibits run as a timeline from the Ice Age to today: listed here in the '
                    'order of its own guide maps, with the photos printed in the 2023 guide. Its collection is not '
                    'online; the objects below the exhibits are ones the museum shows on Google Arts & Culture '
                    '(dolls, finds from the Pequot War battlefields, a dugout canoe and fishing gear), which may not be '
                    'on view now.',
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
    print(f'{works["count"]} exhibits ({sum("image" in a for a in works["artworks"])} with pictures); museum page '
          f'{len(guide["works"])} ({sum(bool(w.get("imageUrl")) for w in guide["works"])} pictures)')
    for k, v in by.items(): print(f'  {k}: {v}')


if __name__ == '__main__':
    sys.exit(main())
