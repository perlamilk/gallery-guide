#!/usr/bin/env python3
"""Build the Museum of Science (Boston) map guide (run: python3 tools/harvest_mos.py, then this).

    data/mos/floors.json       Level 2, Level 1 and the Lower Level, seen from above (flat 2D)
    data/mos/artworks.json     the exhibits, theaters, live presentations and highlights, in the room where they are
    data/mos/images/           pictures from mos.org, made smaller for phones
    data/guides/Q1139748.json  the same, for the museum page

Where the information comes from
--------------------------------
The map is traced from the museum's own visitor map (October 2026, "MoS Map_YVT_Page_1.jpg" on
mos.org/visit/map, cached in .cache/mos/map1.jpg, 1700 x 2200 px). It shows the three levels in three panels, with
the Red, Green and Blue Wings, restrooms, stairs, elevators, the café, store, information desk, lockers and theaters.
Coordinates here are pixels of that picture, times 2. The panels are stacked on the picture, so Level 1 is moved up
652 px and the Lower Level 1322 px, which puts the Blue Wing's walls and stairs on top of each other on all three.
Rooms and amenities are where the museum's map puts them; walls are simplified to straight lines and the hatched
(staff-only) areas are drawn as closed. North is roughly up (the Charles River is at the top of Level 1).

The exhibits: every page under mos.org/visit/exhibits, /live-presentations and /drop-in-activities (tools/harvest_mos.py).
Each page says its "Location" (wing and level). Past exhibits (the page says it closed) are left out. A few pages
give only the wing, and those are placed by guess and say so.
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
OUT = ROOT / 'data' / 'mos'
CACHE = ROOT / '.cache' / 'mos'
MUSEUM = 'Q1139748'
NAME = 'Museum of Science'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
GUESS = '(approximate)'
DY = {'2': 0, '1': 652, 'L': 1322}     # how far each panel sits below Level 2 on the museum's map picture


def P(x, y):
    return [round(x * 2, 1), round(y * 2, 1)]


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# ---- Level 2 ---------------------------------------------------------------------------------------------------
# rooms: (id, kind, name, polygon, short label for galleries)

LEVEL2 = [
    ('Hall of Human Life', 'gallery', 'Hall of Human Life: the body and health, with the axolotls, the bees and the '
     'tamarin monkeys', [(400, 493), (665, 493), (665, 398), (770, 398), (770, 478), (825, 478), (825, 550),
                         (575, 560), (560, 567), (400, 567)], 'Human Life'),
    ('Art of Illusion', 'gallery', 'The Art of Illusion', [(400, 567), (560, 567), (575, 560), (575, 645), (400, 645)],
     'Illusion'),
    ('Green Wing, Level 2', 'corridor', 'Green Wing, Level 2: stairs and elevator',
     [(575, 560), (825, 550), (825, 600), (715, 600), (715, 700), (575, 700)], None),
    ('Restrooms Green L2', 'space', 'Restrooms', rect(715, 600, 800, 700), None),
    ('Bridge L2', 'corridor', 'Walkway between the Green Wing and the Blue Wing', rect(825, 550, 945, 585), None),
    ('Blue Wing, Level 2', 'gallery', 'Blue Wing, Level 2: the balcony over the Current Science stage, Faces of Science',
     [(945, 398), (1435, 398), (1435, 585), (945, 585), (945, 432), (1035, 432), (1035, 550), (1310, 550),
      (1310, 432), (945, 432)], 'Blue Wing'),
    ('Public Science Common', 'gallery', 'William and Charlotte Bloomberg Public Science Common',
     rect(1003, 295, 1375, 398), 'Science Common'),
    ('4-D Theater', 'gallery', '4-D Theater (extra ticket)', rect(945, 585, 1068, 712), '4-D'),
    ('The Light House', 'gallery', 'The Light House', rect(1068, 585, 1145, 712), 'Light'),
    ('Immersive Room', 'gallery', 'Immersive Room', rect(1145, 585, 1240, 712), 'Immersive'),
    ('Innovation: Earth', 'gallery', 'Innovation: Earth', rect(1240, 585, 1290, 712), 'Earth'),
    ('Science in the Park', 'gallery', 'Science in the Park', rect(1290, 585, 1365, 712), 'Park'),
    ('Restrooms Blue L2', 'space', 'Restrooms', rect(1365, 585, 1435, 712), None),
]
LEVEL2_CLOSED = [
    [(400, 645), (575, 645), (575, 700), (800, 700), (800, 600), (825, 600), (825, 830), (400, 830)],
]
LEVEL2_DOORS = [('Hall of Human Life', 'Green Wing, Level 2', (700, 556)), ('Art of Illusion', 'Green Wing, Level 2', (575, 610)),
                ('Hall of Human Life', 'Art of Illusion', (480, 567)), ('Green Wing, Level 2', 'Restrooms Green L2', (715, 650)),
                ('Green Wing, Level 2', 'Bridge L2', (825, 567)), ('Bridge L2', 'Blue Wing, Level 2', (945, 567)),
                ('Blue Wing, Level 2', 'Public Science Common', (1190, 398)), ('Blue Wing, Level 2', '4-D Theater', (1000, 585)),
                ('Blue Wing, Level 2', 'The Light House', (1105, 585)), ('Blue Wing, Level 2', 'Immersive Room', (1190, 585)),
                ('Blue Wing, Level 2', 'Innovation: Earth', (1265, 585)), ('Blue Wing, Level 2', 'Science in the Park', (1328, 585)),
                ('Blue Wing, Level 2', 'Restrooms Blue L2', (1400, 585))]
LEVEL2_AMEN = [('stairs', 628, 618), ('elevator', 670, 675), ('restroom', 753, 652), ('stairs', 978, 430),
               ('stairs', 1400, 430), ('restroom', 1400, 650)]
LEVEL2_LABELS = [('GREEN WING', 600, 370), ('BLUE WING', 900, 370)]

# ---- Level 1 ---------------------------------------------------------------------------------------------------

LEVEL1 = [
    ('Planetarium', 'gallery', 'Charles Hayden Planetarium (extra ticket)',
     [(90, 1040), (135, 995), (205, 995), (255, 1045), (255, 1090), (200, 1120), (140, 1130), (90, 1150)], 'Planetarium'),
    ('Cosmic Light', 'gallery', 'Cosmic Light: the Sun, the planets and a meteorite you can touch',
     [(90, 1150), (140, 1130), (200, 1120), (250, 1100), (250, 1250), (90, 1250)], 'Cosmic Light'),
    ('Omni Theater', 'gallery', 'Mugar Omni Theater (extra ticket). Step-free access: Red Wing elevator',
     [(85, 1330), (280, 1330), (280, 1450), (225, 1505), (140, 1505), (85, 1450)], 'Omni'),
    ('Restrooms Red L1', 'space', 'Restrooms', rect(400, 1170, 445, 1250), None),
    ('Riverview Café', 'space', 'Riverview Café, with windows on the Charles River',
     [(445, 1085), (570, 1085), (570, 1365), (400, 1365), (400, 1330), (445, 1285)], None),
    ('Atrium', 'space', 'Atrium (Red Wing): the Soundstair and Archimedean Excogitation; you may eat your own food here',
     [(90, 1250), (400, 1250), (445, 1250), (445, 1285), (400, 1330), (400, 1365), (830, 1365), (830, 1430),
      (430, 1430), (430, 1505), (330, 1505), (280, 1450), (280, 1330), (90, 1330)], None),
    ('Museum Store', 'space', 'Museum Store', rect(430, 1430, 745, 1505), None),
    ('Main Lobby', 'space', 'Main Lobby: information desk (lost and found, first aid, accessibility), ATM',
     [(830, 1300), (945, 1300), (945, 1505), (745, 1505), (745, 1430), (830, 1430)], None),
    ('Exhibit Halls Entrance', 'corridor', 'Exhibit Halls entrance (show your ticket here)',
     rect(830, 1085, 945, 1300), None),
    ('New England Habitats', 'gallery', 'New England Habitats', rect(607, 1090, 830, 1210), 'Habitats'),
    ('Green Wing, Level 1', 'corridor', 'Green Wing, Level 1: Foucault’s Pendulum, lockers, stairs and elevator',
     rect(600, 1210, 830, 1365), None),
    ('Current Science Center', 'gallery', 'Blue Wing, Level 1: the Gordon Current Science & Technology Center stage',
     rect(945, 1050, 1430, 1240), 'Current Science Center'),
    ('Arctic Adventure', 'gallery', 'Arctic Adventure', rect(1000, 950, 1155, 1050), 'Arctic'),
    ('Engineering Design Workshop', 'gallery', 'Engineering Design Workshop', rect(1155, 950, 1380, 1050),
     'Engineering'),
    ('Box Office', 'space', 'Box Office (tickets)', rect(945, 1240, 1095, 1330), None),
    ('Exploring AI', 'gallery', 'Exploring AI', [(1095, 1240), (1280, 1240), (1280, 1330), (1120, 1330)], 'AI'),
    ('Restrooms Blue L1', 'space', 'Restrooms', rect(1370, 1250, 1425, 1330), None),
    ('Mathematica', 'gallery', 'Mathematica (Charles and Ray Eames, 1981), on the ramp to the Theater of Electricity',
     [(1430, 1050), (1540, 1050), (1540, 1200), (1465, 1200), (1465, 1330), (1430, 1330)], 'Math'),
    ('Restrooms East L1', 'space', 'Restrooms', rect(1540, 1085, 1625, 1200), None),
    ('Theater of Electricity', 'gallery', 'Thomson Theater of Electricity: the giant Van de Graaff generator. '
     'Low-sensory viewing area on this level', rect(1465, 1200, 1625, 1330), 'Electricity'),
    ('Parking Corridor', 'corridor', 'Way to the parking garage (stairs and elevator)', rect(945, 1330, 1630, 1365),
     None),
    ('Front Plaza', 'space', f'Outside: Boston Duck Tours ticket booth (April–November), parking payment kiosks and '
     f'the Rock Garden {GUESS}', rect(945, 1365, 1630, 1460), None),
]
LEVEL1_CLOSED = [
    [(250, 1085), (445, 1085), (445, 1170), (400, 1170), (400, 1250), (250, 1250)],
    rect(1035, 1085, 1180, 1200),       # escalators
]
LEVEL1_DOORS = [('Atrium', 'Cosmic Light', (170, 1250)), ('Cosmic Light', 'Planetarium', (115, 1145)),
                ('Atrium', 'Omni Theater', (250, 1330)), ('Atrium', 'Riverview Café', (420, 1350)),
                ('Atrium', 'Restrooms Red L1', (422, 1250)), ('Atrium', 'Museum Store', (500, 1430)),
                ('Atrium', 'Main Lobby', (830, 1400)), ('Main Lobby', 'Exhibit Halls Entrance', (885, 1300)),
                ('Exhibit Halls Entrance', 'Green Wing, Level 1', (830, 1250)), ('Green Wing, Level 1', 'New England Habitats', (700, 1210)),
                ('Exhibit Halls Entrance', 'Current Science Center', (945, 1150)), ('Current Science Center', 'Arctic Adventure', (1080, 1050)),
                ('Current Science Center', 'Engineering Design Workshop', (1260, 1050)), ('Current Science Center', 'Box Office', (1000, 1240)),
                ('Current Science Center', 'Exploring AI', (1200, 1240)), ('Current Science Center', 'Mathematica', (1430, 1150)),
                ('Current Science Center', 'Restrooms Blue L1', (1398, 1240)), ('Mathematica', 'Theater of Electricity', (1480, 1200)),
                ('Mathematica', 'Restrooms East L1', (1540, 1140)), ('Main Lobby', 'Box Office', (945, 1310)),
                ('Box Office', 'Parking Corridor', (1000, 1330)), ('Main Lobby', 'Front Plaza', (945, 1480))]
LEVEL1_AMEN = [('entrance', 890, 1495), ('info', 785, 1470), ('shop', 590, 1468), ('dining', 495, 1300),
               ('restroom', 422, 1210), ('stairs', 340, 1275), ('elevator', 388, 1275), ('stairs', 633, 1268),
               ('elevator', 675, 1332), ('coat', 780, 1340), ('stairs', 978, 1085), ('stairs', 1400, 1085),
               ('restroom', 1398, 1295), ('restroom', 1570, 1120), ('stairs', 1558, 1350), ('elevator', 1605, 1350),
               ('entrance', 1520, 1350)]
LEVEL1_LABELS = [('Charles River ↑', 640, 1010), ('RED WING', 300, 1540), ('GREEN WING', 700, 1060),
                 ('BLUE WING', 1080, 930), ('Main entrance ↓', 880, 1540), ('To parking garage →', 1540, 1400)]

# ---- Lower Level -----------------------------------------------------------------------------------------------

LOWER = [
    ('Red Wing LL', 'corridor', 'Red Wing, Lower Level: take the Red Wing elevator or stairs from Level 1',
     [(275, 1835), (435, 1835), (435, 1920), (372, 1920), (372, 2040), (275, 2040)], None),
    ('Live Animal Care Center', 'gallery', 'Live Animal Care Center (viewing area)', rect(372, 1920, 425, 2035),
     'Animals'),
    ('Green Wing LL West', 'corridor', 'Green Wing, Lower Level: restrooms', rect(475, 1795, 640, 1875), None),
    ('Science Live! Stage', 'gallery', 'Shapiro Family Science Live! Stage', rect(640, 1760, 760, 1875), 'Stage'),
    ('Colby Room', 'space', 'Colby Room', rect(760, 1760, 830, 1875), None),
    ('Green Wing LL', 'corridor', 'Green Wing, Lower Level: stairs and elevator',
     [(605, 1875), (850, 1875), (850, 1915), (705, 1915), (705, 2040), (605, 2040)], None),
    ('A Bird’s World', 'gallery', 'A Bird’s World', [(705, 1915), (850, 1915), (850, 2035), (735, 2035), (705, 2000)],
     'Birds'),
    ('Charles River Gallery', 'gallery', 'Yawkey Gallery on the Charles River',
     [(830, 1760), (945, 1760), (945, 1915), (850, 1915), (850, 1875), (830, 1875)], 'River'),
    ('To the Moon', 'gallery', 'Blue Wing, Lower Level: To the Moon, with the Apollo capsule', rect(945, 1720, 1440, 1815),
     'To the Moon'),
    ('Natural Beauty', 'gallery', 'Natural Beauty: rocks, minerals and a 1,700-pound meteorite',
     rect(945, 1815, 1440, 1915), 'Natural Beauty'),
    ('Natural Mysteries', 'gallery', 'Natural Mysteries', rect(850, 1915, 1090, 2035), 'Mysteries'),
    ('Take a Closer Look', 'gallery', 'Take a Closer Look', rect(1090, 1915, 1255, 2035), 'Closer Look'),
    ('Dinosaurs', 'gallery', 'Dinosaurs: the T. rex model and Cliff the Triceratops', rect(1255, 1915, 1435, 2035),
     'Dinosaurs'),
    ('Accessible Route LL', 'corridor', 'Step-free way to the Theater of Electricity and Mathematica',
     rect(1440, 1845, 1470, 1915), None),
    ('Theater of Electricity, lower entrance', 'gallery', 'Thomson Theater of Electricity (seats; step-free entrance)',
     rect(1470, 1845, 1620, 2000), 'Electricity'),
]
LOWER_CLOSED = [rect(1035, 1790, 1340, 1880)]          # escalators up
LOWER_DOORS = [('Red Wing LL', 'Live Animal Care Center', (372, 1960)), ('Green Wing LL West', 'Science Live! Stage', (640, 1840)),
               ('Science Live! Stage', 'Colby Room', (760, 1820)), ('Green Wing LL West', 'Green Wing LL', (620, 1875)),
               ('Green Wing LL', 'Science Live! Stage', (700, 1875)), ('Green Wing LL', 'A Bird’s World', (720, 1915)),
               ('Green Wing LL', 'Charles River Gallery', (840, 1895)), ('Charles River Gallery', 'To the Moon', (945, 1790)),
               ('Charles River Gallery', 'Natural Beauty', (945, 1880)), ('Natural Beauty', 'Natural Mysteries', (1000, 1915)),
               ('Natural Beauty', 'Take a Closer Look', (1170, 1915)), ('Natural Beauty', 'Dinosaurs', (1340, 1915)),
               ('To the Moon', 'Natural Beauty', (1200, 1815)), ('Natural Beauty', 'Accessible Route LL', (1440, 1880)),
               ('Accessible Route LL', 'Theater of Electricity, lower entrance', (1470, 1880))]
LOWER_AMEN = [('restroom', 322, 2005), ('stairs', 342, 1890), ('elevator', 400, 1890), ('restroom', 547, 1815),
              ('stairs', 633, 1938), ('elevator', 675, 2000), ('stairs', 978, 1755), ('stairs', 1400, 1755)]
LOWER_LABELS = [('RED WING', 340, 2075), ('GREEN WING', 700, 1740), ('BLUE WING', 1000, 1700)]


LABEL_AT = {'Blue Wing, Level 2': (1172, 490), 'Current Science Center': (1310, 1140), 'Atrium': (200, 1290)}


def floor(fid, label, order, area, rooms, closed, doors, amen, labels, home=None):
    dy = DY[fid]
    mv = lambda q: P(q[0], q[1] - dy)
    rr = []
    for rid, kind, name, poly, short in rooms:
        r = {'id': rid, 'kind': kind, 'name': name, 'poly': [mv(q) for q in poly]}
        if kind == 'gallery': r['label'] = short
        if rid in LABEL_AT: r['labelAt'] = mv(LABEL_AT[rid])
        rr.append(r)
    f = {'id': fid, 'label': label, 'order': order, 'transform': [0.25, 0, 0], 'area': area, 'rooms': rr,
         'closed': [{'poly': [mv(q) for q in c]} for c in closed],
         'amenities': [{'type': t, 'at': mv((x, y))} for t, x, y in amen],
         'labels': [{'text': t, 'kind': 'area', 'at': mv((x, y))} for t, x, y in labels],
         'doors': [{'a': a, 'b': b, 'at': mv(p), 'width': 16, 'axis': 'o'} for a, b, p in doors]}
    if home: f['homeView'] = home
    return f


def inside(pt, poly):
    x, y = pt
    c = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c


def build_floors():
    floors = [
        floor('L', 'Lower Level', 0, 'Dinosaurs · Apollo capsule · Natural Mysteries · Birds · Charles River · '
              'Live animals',
              LOWER, LOWER_CLOSED, LOWER_DOORS, LOWER_AMEN, LOWER_LABELS),
        floor('1', 'Level 1', 1, 'Entrance, tickets · Planetarium · Omni · Café · Store · Habitats · AI · '
              'Theater of Electricity',
              LEVEL1, LEVEL1_CLOSED, LEVEL1_DOORS, LEVEL1_AMEN, LEVEL1_LABELS),
        floor('2', 'Level 2', 2, 'Hall of Human Life · Art of Illusion · 4-D Theater · Light House · '
              'Science in the Park',
              LEVEL2, LEVEL2_CLOSED, LEVEL2_DOORS, LEVEL2_AMEN, LEVEL2_LABELS),
    ]
    for f in floors:
        ids = [r['id'] for r in f['rooms']]
        assert len(ids) == len(set(ids)), f['id']
        for d in f['doors']:
            assert d['a'] in ids and d['b'] in ids, (f['id'], d)
        for a in f['amenities']:
            assert any(inside(a['at'], r['poly']) for r in f['rooms']), (f['id'], a)
    return {'about': 'Built by tools/build_mos.py. Traced from the Museum of Science’s own visitor map (October '
                     '2026, mos.org/visit/map): the three levels, the Red, Green and Blue Wings, restrooms, stairs, '
                     'elevators, café, store and information desk where the museum puts them. Walls are simplified.',
            'source': 'Museum of Science, Museum Map (October 2026)',
            'units': 'pixels of the museum’s map picture x 2; the Charles River is at the top',
            'approximate': False, 'defaultFloor': '1', 'galleryWord': 'Exhibit', 'floors': floors}


# ---- exhibits ----------------------------------------------------------------------------------------------------

def picture(key, url):
    if not url: return None
    raw = CACHE / 'img' / f'{key}.bin'
    if not raw.exists():
        raw.parent.mkdir(parents=True, exist_ok=True)
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '60', '-A', UA, url], capture_output=True).stdout
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
    return f'data/mos/images/{key}.jpg'


# page title -> (room, placed by guess?). Pages not listed here are past exhibits and are left out.
PLACE = {
    'Hall of Human Life': ('Hall of Human Life', False),
    'Biogen Foundation Exploration Hub': ('Hall of Human Life', False),
    'The Art of Illusion': ('Art of Illusion', False),
    'Immersive Room': ('Immersive Room', False),
    'The Light House': ('The Light House', False),
    'Innovation: Earth': ('Innovation: Earth', False),
    'Science in the Park': ('Science in the Park', False),
    'Faces of Science: Ambassadors for Equity': ('Blue Wing, Level 2', True),
    'Our Wild Coast: The Gulf of Maine': ('Public Science Common', False),
    'Wildlife Mystery Match': ('Public Science Common', False),
    'Cosmic Light': ('Cosmic Light', False),
    'New England Habitats': ('New England Habitats', False),
    'Weems Animal Sculptures': ('Green Wing, Level 1', True),
    'Bradford Washburn: The Man Behind the Lens': ('Green Wing, Level 1', True),
    'Arctic Adventure: Exploring with Technology': ('Arctic Adventure', False),
    'Engineering Design Workshop, Powered by MathWorks': ('Engineering Design Workshop', False),
    'Design Challenges': ('Engineering Design Workshop', False),
    'Exploring AI: Making the Invisible Visible': ('Exploring AI', False),
    'Science Now': ('Current Science Center', False),
    'Meet a Scientist': ('Current Science Center', False),
    'Robot Roundup': ('Current Science Center', False),
    'Ship-to-Shore with Nautilus Live!': ('Current Science Center', False),
    'The Future with the Leadership Brainery Founders': ('Current Science Center', False),
    'Mathematica': ('Mathematica', False),
    'Lightning!': ('Theater of Electricity', False),
    'Tesla Coils!': ('Theater of Electricity', False),
    'The Rock Garden': ('Front Plaza', True),
    'To the Moon': ('To the Moon', False),
    'Transportation': ('To the Moon', True),
    'Natural Beauty: The Harold Grinspoon Collection': ('Natural Beauty', False),
    'Natural Mysteries': ('Natural Mysteries', False),
    'Take a Closer Look': ('Take a Closer Look', False),
    'Dinosaurs: Modeling the Mesozoic': ('Dinosaurs', False),
    'Colossal Fossil: Triceratops Cliff': ('Dinosaurs', False),
    'Yawkey Gallery on the Charles River': ('Charles River Gallery', False),
    'Live Animal Care Center': ('Live Animal Care Center', False),
    'Science Live!': ('Science Live! Stage', False),
    'Live Animal Presentation': ('Science Live! Stage', False),
    'Science Storytime': ('Science Live! Stage', False),
    'Supercold Science': ('Science Live! Stage', False),
}
CLOSED_WORDS = re.compile(r'exhibit (?:has )?closed|this is a past exhibit|this exhibit is closed', re.I)

# Theaters and the museum's best-known things, written for this guide from the museum's pages and map.
# (key, room, title, kind, text, picture from the page of)
HIGHLIGHTS = [
    ('planetarium', 'Planetarium', 'Charles Hayden Planetarium', 'Theater',
     'The dome theater for star shows and music-and-light shows. Extra ticket: $6 with Exhibit Halls admission. '
     'Open late on Friday and Saturday nights.', 'Cosmic Light'),
    ('omni', 'Omni Theater', 'Mugar Omni Theater', 'Theater',
     'A five-story domed screen, newly refurbished, for science films and Hollywood classics. Extra ticket: $6 with '
     'Exhibit Halls admission. Step-free access: take the Red Wing elevator on Level 1 up.', None),
    ('4d', '4-D Theater', '4-D Theater', 'Theater',
     'Short 3-D films with motion, wind and water effects. Needs Exhibit Halls admission plus a $6 ticket.', None),
    ('vdg', 'Theater of Electricity', 'The Van de Graaff generator', 'Object',
     'The world’s largest air-insulated Van de Graaff generator, built by Robert J. Van de Graaff in the 1930s. In '
     'the Lightning! show it throws indoor bolts across the Theater of Electricity.', None),
    ('pendulum', 'Green Wing, Level 1', 'Foucault’s Pendulum', 'Object',
     'A heavy ball on a long wire, swinging in the same direction while the Earth turns underneath it: the slow '
     'change in its path shows that the Earth rotates. By the lockers in the Green Wing.', None),
    ('excogitation', 'Atrium', 'Archimedean Excogitation', 'Object',
     'George Rhoads’s big rolling-ball machine in the Atrium: balls climb, drop, ring bells and run through tracks, '
     'one of the museum’s best-loved sights.', None),
    ('soundstair', 'Atrium', 'Soundstair', 'Object',
     'A staircase that plays notes as you climb it, next to Archimedean Excogitation in the Atrium.', None),
    ('apollo', 'To the Moon', 'Apollo and Mercury capsules', 'Object',
     'Full-size models of the Apollo Command Module (step in to watch the first Moon landing) and of a Mercury '
     'capsule, a model of the Lunar Module cockpit and Moon rock fragments.', 'To the Moon'),
    ('trex', 'Dinosaurs', 'Tyrannosaurus rex', 'Object',
     'The museum’s full-size T. rex model, made in 2001 from what over 30 skeletons now show (the first one, from '
     'the 1960s, was based on three incomplete skeletons).', 'Dinosaurs: Modeling the Mesozoic'),
    ('cliff', 'Dinosaurs', 'Cliff the Triceratops', 'Object',
     'A 65-million-year-old Triceratops from the Dakota Badlands, one of the most complete skeletons of its kind '
     'ever found.', 'Colossal Fossil: Triceratops Cliff'),
    ('meteorite', 'Natural Beauty', 'Iron meteorite (1,700 pounds)', 'Object',
     'An iron meteorite that landed on Earth 4,500 years ago, the highlight of Harold Grinspoon’s collection of rocks, '
     'minerals and petrified wood.', 'Natural Beauty: The Harold Grinspoon Collection'),
    ('moose', 'New England Habitats', 'The moose diorama', 'Object',
     'A misty autumn morning in Maine’s moose country, one of the life-size dioramas of New England habitats.',
     'New England Habitats'),
    ('lighthouse', 'The Light House', 'The mirror lighthouse', 'Object',
     'A tall lighthouse covered in hundreds of mirror-like cubes that throw a rainbow of light, at the entrance of '
     'The Light House.', 'The Light House'),
    ('birds', 'A Bird’s World', 'A Bird’s World', 'Exhibit',
     'Mounted birds from the museum’s collection, on the Green Wing’s Lower Level. Shown on the museum’s map; it has no '
     'page of its own.', None),
]


def kind_of(r):
    return {'exhibits': 'Exhibit', 'live-presentations': 'Live presentation',
            'drop-in-activities': 'Drop-in activity'}[r['kind']]


def year_of(text):
    m = re.search(r'opened at the Museum of Science in (\d{4})|Created in \w+ (\d{4})', text or '')
    return int(m[1] or m[2]) if m else None


def build_works(floors):
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    rows = json.loads((CACHE / 'exhibits.json').read_text()) if (CACHE / 'exhibits.json').exists() else None
    if rows is None: raise SystemExit('run tools/harvest_mos.py first')
    by_title = {r['title']: r for r in rows}
    works = []

    def add(a, room, guessed, note):
        fl, gname = rooms[room]
        a.update({'gallery': room, 'galleryName': gname, 'floor': fl, 'placeNote': note})
        if guessed: a['placeGuessed'] = True
        works.append({k: v for k, v in a.items() if v not in (None, '')})

    for r in rows:
        if r['title'] not in PLACE: continue
        if CLOSED_WORDS.search(r['text'][:300]): continue
        room, guessed = PLACE[r['title']]
        slug = r['url'].rstrip('/').rsplit('/', 1)[1]
        key = f'mos-{slug}'
        text = re.sub(r'^Temporary Exhibit\s*', '', r['text'])
        a = {'id': key, 'title': r['title'], 'artist': kind_of(r), 'medium': r['subtitle'] or None,
             'year': year_of(text), 'description': text[:1500] or r['summary'], 'url': r['url'],
             'image': picture(key, r['image']), 'audience': r['audience'] or None, 'price': r['price'] or None}
        if a['image']: a['imageCredit'] = 'Museum of Science, Boston (mos.org)'
        if not r['permanent'] and r['kind'] == 'exhibits': a['temporary'] = True
        note = (f'The museum’s page says “{r["location"]}”; which room is our guess.' if guessed
                else f'Where the museum’s page and map put it ({r["location"]}).')
        add(a, room, guessed, note)
    for key, room, title, kind, text, pic_of in HIGHLIGHTS:
        a = {'id': f'mos-{key}', 'title': title, 'artist': kind, 'description': text, 'url': 'https://www.mos.org/visit/map'}
        src = by_title.get(pic_of)
        if src and src['image']:
            a['image'] = picture('mos-' + src['url'].rstrip('/').rsplit('/', 1)[1], src['image'])
            a['imageCredit'] = f'Museum of Science, Boston (mos.org): {pic_of}'
        add(a, room, False, 'Where the museum’s map puts it.')
    order = {r['id']: i for f in floors['floors'] for i, r in enumerate(f['rooms'])}
    forder = {f['id']: f['order'] for f in floors['floors']}
    works.sort(key=lambda a: (forder[a['floor']], order[a['gallery']], a['artist'] != 'Exhibit', a['title']))
    return {'source': 'Museum of Science, Boston: exhibit pages and Museum Map (mos.org)',
            'checked': time.strftime('%Y-%m-%d'), 'count': len(works), 'complete': True, 'artworks': works}


def build_guide(works):
    rows = []
    for a in works['artworks']:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a['artist'], 'year': a.get('year'),
                     'medium': a.get('medium'), 'url': a['url'], 'imageUrl': a.get('image'), 'onView': True,
                     'gallery': a['gallery'], 'floor': a['floor']}.items() if v not in (None, '')})
    return {'museum': MUSEUM, 'name': NAME, 'checked': time.strftime('%Y-%m-%d'),
            'source': 'Museum of Science, Boston: exhibit pages and Museum Map (mos.org)', 'onViewKnown': True,
            'note': 'A science center: instead of a collection of artworks it has some 700 hands-on exhibits in about '
                    '30 exhibit areas, live presentations and theaters. Listed here are the exhibit areas, the live '
                    'shows and the best-known things to see, in the rooms where the museum’s map puts them.',
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
    print(f'{works["count"]} exhibits, shows and highlights ({sum("image" in a for a in works["artworks"])} with pictures)')
    for k, v in by.items(): print(f'  {k}: {v}')


if __name__ == '__main__':
    sys.exit(main())
