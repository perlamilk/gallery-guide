#!/usr/bin/env python3
"""Build the Springfield Museums (Springfield, MA) map guide: python3 tools/harvest_spfld.py, then this.

    data/spfld/floors.json        the Quadrangle and every floor of the five museums, seen from above (flat 2D)
    data/spfld/artworks.json      the galleries and the works the museums mark "On View", each in its gallery
    data/spfld/images/            their pictures, made smaller for phones
    data/guides/Q7758868.json     the same, for the museum page

Where the information comes from
--------------------------------
The map is traced from the museums' own maps (springfieldmuseums.org/map, cached in .cache/spfld/maps):
  - the Quadrangle: "springfield-museums-campus-map-2017" (buildings, entrances, parking, café, the Dr. Seuss
    Sculpture Garden and its statues). Units: pixels of that map at 878 px wide, x 2. Kept the way the museum draws it
    (State Street at the top, Edwards Street at the bottom).
  - each museum's floors: the museums' floor maps (2020): Science Museum (lower level, floors 1 and 2), G. W. V. Smith
    Art Museum (floors 1-2), D'Amour Museum of Fine Arts (floors 1-2), Amazing World of Dr. Seuss (floors 1-2) and
    Museum of Springfield History (floors 1-2). They show the galleries, restrooms, elevators, stairs, information
    desks and entrances. They are diagrams, not to scale: each floor is turned to face the way the building stands on
    the Quadrangle map and drawn as large as fits over the middle of the Quadrangle view (the app keeps the camera
    still when you change floors). Walls are simplified to straight lines.

The works: the gallery pages under springfieldmuseums.org/about/ (one per gallery, with a photo) and the ~920
collection highlights (springfieldmuseums.org/collections); those whose "On View?" field says Yes are listed, in the
gallery their subject belongs to (the museums don't say which room, so most rooms are our guess and are marked so).
"""
import io
import json
import math
import re
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'spfld'
CACHE = ROOT / '.cache' / 'spfld'
MUSEUM = 'Q7758868'
NAME = 'Springfield Museums'
SITE = 'https://springfieldmuseums.org'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
K = 1                       # map units per pixel of the campus map (878 px wide)


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def ellipse(cx, cy, rx, ry, n=16):
    return [(cx + rx * math.cos(2 * math.pi * i / n), cy + ry * math.sin(2 * math.pi * i / n)) for i in range(n)]


# ---- the Quadrangle (campus map pixels) --------------------------------------------------------------------------
# rooms: (id, kind, name, polygon, short label)
GWVS_OUT = [(158, 503), (273, 503), (273, 858), (165, 858), (165, 825), (150, 825), (150, 795), (158, 795)]
SSM_OUT = [(38, 1005), (285, 1005), (285, 1240), (152, 1240), (152, 1355), (38, 1355)]
DMFA_OUT = rect(533, 1017, 805, 1208)
AWDS_OUT = [(327, 1283), (517, 1283), (517, 1357), (445, 1357), (445, 1405), (395, 1405), (395, 1357), (327, 1357)]
WMSH_OUT = [(418, 1815), (495, 1815), (495, 1757), (772, 1757), (772, 1965), (418, 1965)]
# The app keeps the camera where it is when you change floors, so every museum's floors are drawn over the middle
# of the Quadrangle view (this box), as large as fits, turned the way the building faces on the Quadrangle map.
FIT = (191, 794, 651, 1674)

Q = [
    ('Quadrangle', 'corridor', 'The Quadrangle: lawns and walks between the five museums (free to walk around)',
     [(95, 470), (525, 470), (525, 515), (830, 520), (830, 1680), (95, 1680)], None),
    ('Science Museum building', 'space', 'Springfield Science Museum, with the Welcome Center: pick Science floor LL, 1 '
     'or 2 above to see its halls', SSM_OUT, None),
    ('Welcome Center', 'space', 'Welcome Center (in the Science Museum): tickets for all five museums, information, '
     'restrooms', rect(152, 1240, 285, 1272), None),
    ('Smith Art Museum building', 'space', 'George Walter Vincent Smith Art Museum: pick Smith floor 1 or 2 above',
     GWVS_OUT, None),
    ("D'Amour building", 'space', "Michele & Donald D'Amour Museum of Fine Arts: pick Fine Arts floor 1 or 2 above",
     DMFA_OUT, None),
    ('Seuss building', 'space', 'The Amazing World of Dr. Seuss Museum: pick Seuss floor 1 or 2 above', AWDS_OUT, None),
    ('History building', 'space', 'Lyman & Merrie Wood Museum of Springfield History (across Edwards Street): pick '
     'History floor 1 or 2 above', WMSH_OUT, None),
    ('Sculpture Garden', 'gallery', 'Dr. Seuss National Memorial Sculpture Garden (free, open every day)',
     rect(313, 733, 477, 1188), 'Sculpture Garden'),
    ('Yertle Garden', 'gallery', 'Yertle Garden (part of the Sculpture Garden)', ellipse(705, 1268, 62, 24), 'Yertle'),
    ('Merrick Park', 'gallery', 'Merrick Park, with Augustus Saint-Gaudens’ The Puritan',
     [(560, 262), (745, 262), (705, 520), (525, 515), (560, 400)], 'Merrick Park'),
    ('Blake House Café', 'space', 'Blake House Café (1839, the oldest building on the Quadrangle): Tue–Sun 11 am–3 pm; '
     'no museum ticket needed', [(345, 1515), (422, 1515), (422, 1635), (345, 1635)], None),
    ('Lot by the Smith', 'space', 'Parking by the Smith Art Museum: accessible spaces', rect(118, 868, 262, 1000), None),
    ('Edwards Street lot', 'space', 'Free parking (Edwards Street lot, by the Welcome Center): accessible spaces, EV '
     'charging', rect(110, 1440, 305, 1680), None),
    ('Lot across Edwards Street', 'space', 'Free parking across Edwards Street', rect(45, 1730, 328, 1910), None),
    ('State Street lot', 'space', 'Free parking on State Street, across from the City Library', rect(165, 55, 470, 125),
     None),
]
Q_CLOSED = [rect(118, 313, 537, 465),                                     # Springfield City Library
            [(568, 632), (690, 632), (690, 650), (800, 650), (800, 750), (830, 750), (830, 980), (565, 975),
             (565, 750), (535, 715)],                                       # Christ Church Cathedral
            rect(660, 1367, 797, 1420),                                     # Kilroy House (offices)
            rect(638, 1580, 788, 1650)]
Q_DOORS = [('Quadrangle', 'Smith Art Museum building', (273, 540)), ('Quadrangle', "D'Amour building", (533, 1100)),
           ('Quadrangle', 'Seuss building', (420, 1283)), ('Quadrangle', 'Welcome Center', (225, 1272)),
           ('Quadrangle', 'Sculpture Garden', (395, 1188)), ('Quadrangle', 'Blake House Café', (383, 1515)),
           ('Quadrangle', 'Edwards Street lot', (220, 1440)), ('Quadrangle', 'Lot by the Smith', (262, 935))]
Q_AMEN = [('entrance', 225, 1262), ('info', 185, 1256), ('entrance', 265, 540), ('entrance', 545, 1100),
          ('entrance', 420, 1293), ('entrance', 450, 1827), ('dining', 383, 1590), ('restroom', 255, 1256)]
Q_LABELS = [('STATE STREET', 'area', 418, 175), ('EDWARDS STREET', 'area', 415, 1712),
            ('CHESTNUT STREET', 'area', 850, 1100), ('Springfield City Library', 'area', 325, 390),
            ('Christ Church Cathedral', 'area', 690, 810), ('Kilroy House (offices)', 'area', 728, 1393),
            ('North Lawn', 'area', 583, 1508)]

# ---- each museum's floors (pixels of its own floor map) ---------------------------------------------------------
# Science Museum, first floor (412 x 647); entrance at the bottom
S1 = [
    ('Mammal Hall', 'gallery', 'Mammal Hall', rect(143, 78, 355, 160), 'Mammals'),
    ('Native American Hall', 'gallery', 'Native American Hall', rect(143, 160, 222, 330), 'Native American'),
    ('Habitat Hall', 'gallery', 'Habitat Hall', rect(280, 160, 328, 365), 'Habitat'),
    ('Ramp', 'corridor', 'Ramp to the second floor (Upper African Hall)', rect(8, 155, 143, 320), None),
    ('African Hall', 'gallery', 'R. E. Phelon African Hall', rect(8, 320, 143, 385), 'African Hall'),
    ('Dinosaur Hall', 'gallery', 'Dinosaur Hall: the Tyrannosaurus rex replica', rect(8, 385, 143, 510), 'Dinosaurs'),
    ('Tolman Hall', 'gallery', 'Tolman Hall', rect(8, 510, 112, 640), 'Tolman Hall'),
    ('Science Stairs 1', 'corridor', 'Stairs', rect(222, 160, 280, 365), None),
    ('Science Store', 'space', 'Museum Store', rect(182, 365, 330, 470), None),
    ('Science Hall 1', 'corridor', 'Hall: stairs, elevator, restrooms, information', [
        (143, 365), (182, 365), (182, 470), (405, 470), (405, 490), (182, 490), (182, 640), (112, 640), (112, 510),
        (143, 510)], None),
    ('Science Welcome Center', 'space', 'Welcome Center: museum admissions for all five museums',
     rect(182, 490, 405, 560), None),
]
S1_CLOSED = [rect(143, 330, 222, 365), rect(330, 365, 405, 470)]
S1_DOORS = [('Mammal Hall', 'Native American Hall', (180, 160)), ('Mammal Hall', 'Habitat Hall', (305, 160)),
            ('Ramp', 'African Hall', (75, 320)), ('African Hall', 'Dinosaur Hall', (75, 385)),
            ('Dinosaur Hall', 'Tolman Hall', (60, 510)), ('Dinosaur Hall', 'Science Hall 1', (143, 470)),
            ('Science Hall 1', 'Science Store', (182, 420)), ('Science Hall 1', 'Science Welcome Center', (182, 525)),
            ('Science Hall 1', 'Tolman Hall', (112, 590)), ('Native American Hall', 'Ramp', (143, 250)),
            ('Habitat Hall', 'Science Store', (305, 365)), ('Science Stairs 1', 'Science Store', (250, 365))]
S1_AMEN = [('entrance', 290, 552), ('info', 330, 515), ('shop', 255, 420), ('elevator', 163, 520),
           ('restroom', 163, 550), ('restroom-all', 125, 590), ('info', 163, 628), ('stairs', 160, 595),
           ('stairs', 160, 400), ('stairs', 252, 250)]
S1_LABELS = []

# second floor (419 x 439)
S2 = [
    ('Changing Exhibitions (Science)', 'gallery', 'Changing Exhibitions', rect(150, 63, 412, 150), 'Changing'),
    ('Upper African Hall', 'gallery', 'Upper African Hall (top of the ramp)', rect(3, 135, 150, 430), 'Upper African'),
    ('SparkLab', 'gallery', 'SparkLab: hands-on science', rect(150, 150, 222, 312), 'SparkLab'),
    ('Science Stairs 2', 'corridor', 'Stairs', rect(222, 150, 258, 312), None),
    ('Space Station', 'gallery', 'Space Station (coming soon)', rect(258, 150, 357, 225), 'Space Station'),
    ('Seymour Planetarium', 'gallery', 'Seymour Planetarium (shows at set times)', rect(258, 225, 357, 312),
     'Planetarium'),
    ('Astronomy Hall', 'gallery', 'Astronomy Hall', rect(150, 312, 333, 345), 'Astronomy'),
    ('Earth Hall', 'gallery', 'Earth Hall: minerals, fossils and the Earth', rect(150, 345, 330, 435), 'Earth Hall'),
    ('Science Workshop', 'gallery', 'Science Workshop', rect(330, 345, 412, 435), 'Workshop'),
]
S2_CLOSED = [rect(333, 312, 357, 345)]
S2_DOORS = [('Upper African Hall', 'SparkLab', (150, 250)), ('SparkLab', 'Changing Exhibitions (Science)', (190, 150)),
            ('Science Stairs 2', 'Changing Exhibitions (Science)', (240, 150)),
            ('Science Stairs 2', 'Astronomy Hall', (240, 312)), ('SparkLab', 'Astronomy Hall', (185, 312)),
            ('Astronomy Hall', 'Seymour Planetarium', (300, 312)), ('Space Station', 'Seymour Planetarium', (310, 225)),
            ('Astronomy Hall', 'Earth Hall', (240, 345)), ('Earth Hall', 'Science Workshop', (330, 395))]
S2_AMEN = [('stairs', 240, 230), ('elevator', 165, 420)]
S2_LABELS = []

# lower level (595 x 280)
S0 = [
    ('Live Animal Center', 'gallery', 'Solutia Live Animal Center & Aquarium', rect(3, 85, 112, 205), 'Live Animals'),
    ('Connecticut River Exhibit', 'gallery', 'Connecticut River Exhibit', rect(112, 100, 195, 170), 'CT River'),
    ('Exploration Center', 'gallery', 'Exploration Center', rect(195, 100, 298, 170), 'Exploration'),
    ('Discovery Lab', 'gallery', 'Masspower Science Discovery Lab', rect(298, 95, 385, 170), 'Discovery Lab'),
    ('Reptile Wall', 'gallery', 'Reptile Wall (along the hall)', rect(112, 170, 385, 205), 'Reptile Wall'),
    ('Investigation Station', 'gallery', 'Investigation Station and Watershed Table (limited hours)',
     rect(385, 125, 520, 205), 'Investigation'),
    ('Lower Restrooms', 'space', 'Restrooms, accessible restroom, water fountain, information',
     rect(390, 55, 520, 125), None),
    ('Lower Lobby', 'corridor', 'Stairs and elevator (from the first floor)', rect(55, 205, 240, 250), None),
]
S0_CLOSED = []
S0_DOORS = [('Live Animal Center', 'Connecticut River Exhibit', (112, 135)),
            ('Connecticut River Exhibit', 'Reptile Wall', (150, 170)), ('Exploration Center', 'Reptile Wall', (245, 170)),
            ('Discovery Lab', 'Reptile Wall', (340, 170)), ('Reptile Wall', 'Investigation Station', (385, 188)),
            ('Investigation Station', 'Lower Restrooms', (455, 125)), ('Reptile Wall', 'Lower Lobby', (180, 205)),
            ('Live Animal Center', 'Lower Lobby', (90, 205))]
S0_AMEN = [('restroom-all', 407, 72), ('water', 437, 102), ('info', 467, 102), ('restroom', 497, 102),
           ('elevator', 122, 228), ('stairs', 85, 228), ('stairs', 220, 228)]
S0_LABELS = []

# G. W. V. Smith Art Museum, first floor (308 x 837); entrance on the right, near the top
A1 = [
    ('Japanese Arms & Armor', 'gallery', 'Japanese Arms & Armor', rect(3, 63, 218, 190), 'Arms & Armor'),
    ('Italian Paintings', 'gallery', 'Italian Paintings (The Grand Tour: George and Belle Smith collect in Italy)',
     rect(97, 190, 155, 320), 'Italian'),
    ('Smith Lobby', 'corridor', 'Entrance and stairs down to the studios', [
        (218, 63), (290, 63), (290, 265), (192, 265), (192, 190), (218, 190)], None),
    ('Smith Hall 1', 'corridor', 'Hall: elevator', [(155, 190), (192, 190), (192, 290), (230, 290), (230, 265),
                                                     (192, 265), (192, 400), (90, 400), (90, 372), (25, 372),
                                                     (25, 320), (155, 320)], None),
    ('Smith Restrooms', 'space', 'Restrooms, accessible restroom, information', rect(192, 290, 230, 400), None),
    ('Plaster Cast Gallery', 'gallery', 'Plaster Cast Gallery', rect(25, 400, 230, 640), 'Plaster Casts'),
    ('Changing Exhibitions (Smith)', 'gallery', 'Changing Exhibitions', rect(10, 640, 240, 830), 'Changing'),
]
A1_CLOSED = [rect(25, 193, 97, 318), rect(25, 372, 90, 398)]
A1_DOORS = [('Japanese Arms & Armor', 'Smith Lobby', (218, 120)), ('Smith Lobby', 'Smith Hall 1', (192, 225)),
            ('Smith Hall 1', 'Italian Paintings', (155, 260)), ('Smith Hall 1', 'Smith Restrooms', (192, 340)),
            ('Smith Hall 1', 'Plaster Cast Gallery', (120, 400)),
            ('Plaster Cast Gallery', 'Changing Exhibitions (Smith)', (130, 640))]
A1_AMEN = [('entrance', 270, 157), ('stairs', 265, 100), ('elevator', 57, 343), ('restroom', 213, 305),
           ('restroom-all', 213, 340), ('info', 213, 378)]
A1_LABELS = []

# second floor
A2 = [
    ('American Paintings Salon', 'gallery', 'American Paintings Salon', rect(22, 68, 268, 200), 'American Salon'),
    ('Chinese Cloisonné', 'gallery', 'Chinese Cloisonné', rect(33, 200, 240, 360), 'Cloisonné'),
    ('Hasbro Games Art Discovery Center', 'gallery', 'Hasbro Games Art Discovery Center: hands-on art for families',
     rect(240, 200, 290, 693), 'Hasbro Games'),
    ('Japanese Decorative Arts', 'gallery', 'Japanese Decorative Arts', rect(33, 360, 240, 440), 'Japanese Dec. Arts'),
    ('Chinese Jade', 'gallery', 'Chinese Jade', rect(33, 440, 92, 645), 'Jade'),
    ('Chinese Porcelain', 'gallery', 'Chinese Porcelain', rect(92, 440, 182, 690), 'Porcelain'),
    ('Japanese Bronzes', 'gallery', 'Japanese Bronzes', rect(182, 440, 240, 690), 'Bronzes'),
    ('Islamic World', 'gallery', 'The Art of the Islamic World', rect(20, 690, 240, 835), 'Islamic World'),
]
A2_CLOSED = [rect(33, 200, 90, 237), rect(33, 645, 92, 690)]
A2_DOORS = [('American Paintings Salon', 'Chinese Cloisonné', (130, 200)),
            ('Chinese Cloisonné', 'Hasbro Games Art Discovery Center', (240, 300)),
            ('Chinese Cloisonné', 'Japanese Decorative Arts', (150, 360)),
            ('Japanese Decorative Arts', 'Chinese Jade', (62, 440)),
            ('Japanese Decorative Arts', 'Chinese Porcelain', (137, 440)),
            ('Japanese Decorative Arts', 'Japanese Bronzes', (210, 440)),
            ('Chinese Porcelain', 'Islamic World', (137, 690)), ('Japanese Bronzes', 'Islamic World', (210, 690))]
A2_AMEN = [('stairs', 248, 110), ('elevator', 60, 343)]
A2_LABELS = []

# D'Amour Museum of Fine Arts, first floor (391 x 614); entrance at the bottom
F1 = [
    ('Early 20th-Century American', 'gallery', 'Early 20th-Century American', rect(123, 57, 283, 140), 'Early 20th C.'),
    ('Fine Arts NE Hall', 'corridor', 'Hall: elevator, way to ArtSpace', rect(283, 57, 388, 180), None),
    ('Print Gallery', 'gallery', 'Print Gallery', rect(248, 140, 283, 235), 'Prints'),
    ('Fine Arts Services', 'space', 'Restrooms, accessible restroom, information; stairs down to the Davis Auditorium',
     rect(248, 235, 283, 445), None),
    ('Blake Court', 'gallery', 'Blake Court (19th-Century American), under the skylight', rect(157, 140, 248, 400),
     'Blake Court'),
    ('Community Gallery', 'gallery', 'Community Gallery', rect(123, 140, 157, 410), 'Community'),
    ('Deco Function Room', 'space', 'The Deco Function Room', rect(3, 210, 123, 375), None),
    ('Alpert Gallery', 'gallery', 'Alpert Gallery', rect(3, 375, 123, 480), 'Alpert'),
    ('Modern & Contemporary Gallery', 'gallery', 'Modern & Contemporary Gallery', rect(283, 180, 388, 420),
     'Modern & Contemporary'),
    ('Starr Gallery', 'gallery', 'Starr Gallery', rect(283, 420, 388, 500), 'Starr'),
    ('Fine Arts Hall 1', 'corridor', 'Central hall', [(123, 410), (157, 410), (157, 400), (248, 400), (248, 445),
                                                       (283, 445), (283, 500), (123, 500), (123, 480)], None),
    ('Fuller Gallery', 'gallery', 'Fuller Gallery (18th-Century American)', rect(3, 495, 170, 605), 'Fuller'),
    ('Fine Arts Lobby', 'corridor', 'Entrance lobby', rect(170, 500, 245, 605), None),
    ('19th-Century American', 'gallery', '19th-Century American', rect(245, 500, 388, 605), '19th C. American'),
]
F1_CLOSED = [rect(3, 57, 123, 210)]
F1_DOORS = [('Fine Arts Lobby', 'Fine Arts Hall 1', (207, 500)), ('Fine Arts Lobby', 'Fuller Gallery', (170, 560)),
            ('Fine Arts Lobby', '19th-Century American', (245, 560)), ('Fine Arts Hall 1', 'Alpert Gallery', (123, 455)),
            ('Fine Arts Hall 1', 'Starr Gallery', (283, 470)), ('Fine Arts Hall 1', 'Blake Court', (200, 400)),
            ('Fine Arts Hall 1', 'Community Gallery', (140, 410)),
            ('Community Gallery', 'Deco Function Room', (123, 290)),
            ('Community Gallery', 'Early 20th-Century American', (140, 140)),
            ('Early 20th-Century American', 'Fine Arts NE Hall', (283, 100)),
            ('Fine Arts NE Hall', 'Print Gallery', (265, 140)), ('Print Gallery', 'Fine Arts Services', (265, 235)),
            ('Fine Arts NE Hall', 'Modern & Contemporary Gallery', (335, 180)),
            ('Fine Arts Services', 'Fine Arts Hall 1', (265, 445)), ('Blake Court', 'Print Gallery', (248, 160))]
F1_AMEN = [('entrance', 207, 590), ('restroom', 265, 245), ('restroom-all', 265, 270), ('info', 265, 298),
           ('stairs', 265, 420), ('stairs', 200, 385), ('elevator', 366, 155)]
F1_LABELS = []

# second floor (390 x 609)
F2 = [
    ('Leary Gallery', 'gallery', 'Leary Gallery (French Impressionism)', rect(3, 70, 105, 160), 'Impressionism'),
    ('19th-Century French', 'gallery', '19th-Century French', rect(3, 160, 105, 285), '19th C. French'),
    ('18th-Century Italian', 'gallery', '18th-Century Italian', rect(3, 285, 105, 375), '18th C. Italian'),
    ('17th-Century Flemish', 'gallery', '17th-Century Flemish', rect(3, 375, 105, 435), 'Flemish'),
    ('17th-Century Dutch', 'gallery', '17th-Century Dutch', rect(3, 435, 105, 500), 'Dutch'),
    ('Friedmann Gallery', 'gallery', 'Friedmann Gallery (18th-Century French)', rect(3, 500, 135, 605),
     '18th C. French'),
    ('20th-Century European', 'gallery', '20th-Century European', rect(105, 160, 135, 500), '20th C. European'),
    ('Changing Exhibitions (Fine Arts)', 'gallery', 'Changing Exhibitions',
     [(105, 108), (300, 108), (300, 500), (255, 500), (255, 160), (105, 160)], 'Changing'),
    ('Fine Arts Stairs 2', 'corridor', 'Open stairs down to Blake Court', rect(135, 160, 255, 445), None),
    ('Fine Arts Landing', 'corridor', 'Landing', rect(135, 445, 255, 500), None),
    ('Fine Arts NE Hall 2', 'corridor', 'Elevator', rect(300, 128, 388, 165), None),
    ('Wheeler Gallery', 'gallery', 'Wheeler Gallery (changing exhibitions)', rect(300, 165, 388, 445), 'Wheeler'),
    ('Late Medieval', 'gallery', 'Late Medieval', rect(300, 445, 388, 500), 'Medieval'),
    ('Blake Gallery', 'gallery', 'Blake Gallery (Italian Baroque)', rect(135, 500, 255, 605), 'Italian Baroque'),
    ('Northern Renaissance', 'gallery', 'Northern European & Italian Renaissance', rect(255, 500, 388, 605),
     'Renaissance'),
]
F2_CLOSED = [rect(105, 70, 300, 108), rect(300, 70, 388, 128)]
F2_DOORS = [('Leary Gallery', '19th-Century French', (55, 160)), ('19th-Century French', '18th-Century Italian', (55, 285)),
            ('18th-Century Italian', '17th-Century Flemish', (55, 375)), ('17th-Century Flemish', '17th-Century Dutch', (55, 435)),
            ('17th-Century Dutch', 'Friedmann Gallery', (55, 500)), ('20th-Century European', 'Leary Gallery', (105, 130)),
            ('20th-Century European', '19th-Century French', (105, 220)),
            ('20th-Century European', 'Fine Arts Landing', (135, 470)),
            ('Fine Arts Stairs 2', 'Fine Arts Landing', (195, 445)), ('Fine Arts Landing', 'Blake Gallery', (195, 500)),
            ('Fine Arts Landing', 'Changing Exhibitions (Fine Arts)', (255, 470)),
            ('Changing Exhibitions (Fine Arts)', 'Fine Arts NE Hall 2', (300, 145)),
            ('Fine Arts NE Hall 2', 'Wheeler Gallery', (345, 165)), ('Wheeler Gallery', 'Late Medieval', (345, 445)),
            ('Late Medieval', 'Northern Renaissance', (345, 500)), ('Blake Gallery', 'Northern Renaissance', (255, 555)),
            ('Friedmann Gallery', 'Blake Gallery', (135, 555)),
            ('Changing Exhibitions (Fine Arts)', 'Northern Renaissance', (278, 500))]
F2_AMEN = [('stairs', 165, 400), ('stairs', 230, 400), ('elevator', 366, 147)]
F2_LABELS = [('Open to Blake Court below', 'note', 195, 250)]

# Amazing World of Dr. Seuss, first floor (572 x 490); entrance at the bottom
D1 = [
    ('Whoville', 'gallery', 'Whoville', [(245, 85), (350, 85), (350, 230), (320, 230), (320, 218), (280, 218),
                                         (280, 160), (245, 160)], 'Whoville'),
    ('Seuss Coat Room', 'space', 'Coat room and restrooms', rect(175, 160, 280, 218), None),
    ('Seuss Elevator', 'corridor', 'Elevator', rect(105, 175, 175, 230), None),
    ('Young Ted in Springfield', 'gallery', 'Young Ted in Springfield',
     [(3, 230), (248, 230), (248, 350), (130, 350), (130, 395), (3, 395)], 'Young Ted'),
    ('Fairfield Street', 'gallery', 'Fairfield Street', rect(130, 350, 248, 455), 'Fairfield St'),
    ('Mulberry Street', 'gallery', 'Mulberry Street: the entry hall, with stairs down to the Cat’s Corner and Pet Shop',
     [(248, 218), (320, 218), (320, 455), (248, 455)], 'Mulberry St'),
    ('Readingville', 'gallery', 'Readingville', [(320, 230), (570, 230), (570, 395), (440, 395), (440, 350),
                                                 (320, 350)], 'Readingville'),
    ("Oh, the Places You'll Go", 'gallery', 'Oh, the Places You’ll Go!', rect(320, 350, 440, 455), 'Places'),
]
D1_CLOSED = [rect(215, 63, 245, 160), rect(282, 63, 348, 85)]
D1_DOORS = [('Mulberry Street', 'Whoville', (300, 218)), ('Mulberry Street', 'Young Ted in Springfield', (248, 290)),
            ('Mulberry Street', 'Fairfield Street', (248, 420)), ('Mulberry Street', 'Readingville', (320, 290)),
            ('Mulberry Street', "Oh, the Places You'll Go", (320, 420)),
            ('Seuss Coat Room', 'Young Ted in Springfield', (215, 230)),
            ('Seuss Elevator', 'Young Ted in Springfield', (140, 230)), ('Whoville', 'Seuss Coat Room', (280, 190))]
D1_AMEN = [('entrance', 285, 445), ('stairs', 305, 300), ('restroom', 302, 105), ('restroom', 197, 200),
           ('coat', 250, 190), ('elevator', 150, 200)]
D1_LABELS = []

# second floor
D2 = [
    ('Ted2Ted', 'gallery', 'Ted2Ted', [(3, 265), (105, 265), (105, 250), (248, 250), (248, 385), (3, 385)], 'Ted2Ted'),
    ('Seuss Elevator 2', 'corridor', 'Elevator', rect(122, 200, 178, 250), None),
    ('Seuss Stairs 2', 'corridor', 'Stairs', rect(248, 250, 320, 385), None),
    ('Sal Da Who', 'gallery', 'Sal Da Who: The Making of the Sculpture Garden', rect(350, 255, 570, 385), 'Sal Da Who'),
    ('Ted, Dr. Seuss', 'gallery', 'Ted, Dr. Seuss', rect(130, 385, 437, 488), 'Ted, Dr. Seuss'),
]
D2_CLOSED = [rect(215, 95, 350, 250), rect(320, 250, 350, 360), rect(105, 210, 122, 265), rect(437, 385, 570, 435)]
D2_DOORS = [('Seuss Elevator 2', 'Ted2Ted', (150, 250)), ('Ted2Ted', 'Ted, Dr. Seuss', (190, 385)),
            ('Seuss Stairs 2', 'Ted, Dr. Seuss', (285, 385)), ('Ted, Dr. Seuss', 'Sal Da Who', (400, 385)),
            ('Seuss Stairs 2', 'Sal Da Who', (335, 372))]
D2_AMEN = [('elevator', 150, 225), ('stairs', 285, 320)]
D2_LABELS = []

# Museum of Springfield History, first floor (328 x 681); entrance at the top right
H1 = [
    ('History Coat Room', 'space', 'Coat room', rect(15, 50, 90, 85), None),
    ('MassMutual Hall', 'gallery', 'MassMutual Hall', [(90, 50), (245, 50), (245, 150), (85, 150), (85, 85), (90, 85)],
     'MassMutual Hall'),
    ('Early Transportation', 'gallery', 'Early Transportation', rect(15, 150, 192, 235), 'Early Transport'),
    ('Automobile Gallery', 'gallery', 'Automobile Gallery: cars made in Springfield (Rolls-Royce, Duryea, Knox)',
     [(15, 235), (192, 235), (192, 345), (125, 345), (125, 500), (15, 500)], 'Automobiles'),
    ('History Restrooms', 'space', 'Restrooms and information', rect(125, 345, 192, 465), None),
    ('SIS Hall', 'gallery', 'SIS Hall', [(192, 150), (245, 150), (245, 215), (325, 215), (325, 495), (235, 495),
                                         (235, 465), (192, 465)], 'SIS Hall'),
    ('History Hall 1', 'corridor', 'Stairs up to the second floor and elevator', rect(125, 465, 175, 590), None),
    ('Made in the Valley', 'gallery', 'Made in the Valley', rect(15, 500, 125, 590), 'Made in the Valley'),
    ('Police & Fire', 'gallery', 'Police & Fire Exhibit; stairs down to the History Library & Archives',
     rect(15, 590, 190, 680), 'Police & Fire'),
    ('Hasbro Gameland', 'gallery', 'Hasbro Gameland: games to play', rect(245, 495, 325, 680), 'Hasbro Gameland'),
]
H1_CLOSED = [rect(15, 85, 85, 150), rect(175, 495, 235, 555), rect(190, 590, 245, 680)]
H1_DOORS = [('History Coat Room', 'MassMutual Hall', (90, 68)), ('MassMutual Hall', 'Early Transportation', (140, 150)),
            ('MassMutual Hall', 'SIS Hall', (220, 150)), ('Early Transportation', 'Automobile Gallery', (100, 235)),
            ('Automobile Gallery', 'Made in the Valley', (70, 500)), ('Made in the Valley', 'Police & Fire', (70, 590)),
            ('Automobile Gallery', 'History Hall 1', (125, 480)), ('History Hall 1', 'Police & Fire', (150, 590)),
            ('History Hall 1', 'SIS Hall', (175, 470)), ('SIS Hall', 'Hasbro Gameland', (285, 495)),
            ('History Restrooms', 'SIS Hall', (192, 400))]
H1_AMEN = [('entrance', 235, 68), ('coat', 50, 68), ('stairs', 42, 168), ('restroom', 160, 375), ('info', 160, 437),
           ('stairs', 160, 480), ('elevator', 155, 540), ('stairs', 168, 610)]
H1_LABELS = []

# second floor (326 x 597)
H2 = [
    ('History Stairs NW', 'corridor', 'Stairs', rect(15, 63, 65, 100), None),
    ('Downtown Retail', 'gallery', 'Downtown Retail', rect(65, 63, 185, 125), 'Downtown Retail'),
    ('Smith & Wesson Gallery', 'gallery', 'Smith & Wesson Gallery of Firearms History',
     [(15, 100), (65, 100), (65, 125), (185, 125), (185, 170), (110, 170), (110, 270), (15, 270)], 'Smith & Wesson'),
    ('Changing Exhibits (History)', 'gallery', 'Changing Exhibits', rect(110, 170, 185, 270), 'Changing'),
    ('Civil War', 'gallery', 'John Brown, Abraham Lincoln, & the Civil War', rect(15, 270, 110, 370), 'Civil War'),
    ('History Restrooms 2', 'space', 'Restrooms and information', rect(110, 270, 185, 375), None),
    ('Upper Balcony', 'corridor', 'Upper balcony over the SIS Hall', rect(185, 125, 210, 375), None),
    ('Gee Bee Aviation', 'gallery', 'Gee Bee Aviation: the Granville Brothers’ racing planes',
     [(210, 125), (325, 125), (325, 410), (270, 410), (270, 375), (210, 375)], 'Gee Bee'),
    ('History Landing 2', 'corridor', 'Stairs landing', rect(110, 375, 270, 410), None),
    ('Early Bicycles', 'gallery', 'Early Bicycles', rect(15, 370, 110, 470), 'Bicycles'),
    ('History Elevator 2', 'corridor', 'Elevator', rect(110, 410, 170, 470), None),
    ('Indian Motocycle Collection', 'gallery', 'The Esta Manthos Indian Motocycle Collection',
     [(170, 410), (325, 410), (325, 590), (15, 590), (15, 470), (170, 470)], 'Indian Motocycles'),
]
H2_CLOSED = []
H2_DOORS = [('History Stairs NW', 'Smith & Wesson Gallery', (40, 100)), ('Downtown Retail', 'Smith & Wesson Gallery', (120, 125)),
            ('Smith & Wesson Gallery', 'Changing Exhibits (History)', (147, 170)),
            ('Smith & Wesson Gallery', 'Civil War', (60, 270)), ('Civil War', 'Early Bicycles', (60, 370)),
            ('Early Bicycles', 'Indian Motocycle Collection', (60, 470)),
            ('Early Bicycles', 'History Landing 2', (110, 390)), ('History Landing 2', 'Upper Balcony', (197, 375)),
            ('History Landing 2', 'Gee Bee Aviation', (240, 375)),
            ('History Landing 2', 'History Elevator 2', (140, 410)),
            ('History Landing 2', 'Indian Motocycle Collection', (220, 410)),
            ('History Restrooms 2', 'History Landing 2', (147, 375))]
H2_AMEN = [('stairs', 30, 80), ('info', 128, 300), ('restroom', 145, 348), ('stairs', 210, 395),
           ('elevator', 147, 455)]
H2_LABELS = []

# which way each museum's plan is turned to match the Quadrangle map, and its plan's size
TURN = {'S': 0, 'A': 0, 'F': 90, 'D': 180, 'H': -90}
SIZE = {'S0': (595, 280), 'S1': (412, 647), 'S2': (419, 439), 'A1': (308, 837), 'A2': (308, 837),
        'F1': (391, 614), 'F2': (390, 609), 'D1': (572, 490), 'D2': (572, 490), 'H1': (328, 681), 'H2': (326, 597)}


def turn(p, deg, size):
    x, y = p
    w, h = size
    if deg == 90: return (h - y, x)          # clockwise: the plan's bottom (entrance) faces left
    if deg == -90: return (y, w - x)         # anticlockwise: the plan's top right goes to the top left
    if deg == 180: return (w - x, h - y)
    return (x, y)


def placer(fid, polys):
    """A function that puts a point of this floor's plan into the Quadrangle map's frame."""
    deg = TURN[fid[0]]
    pts = [turn(p, deg, SIZE[fid]) for poly in polys for p in poly]
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    bx0, by0, bx1, by1 = FIT
    s = min((bx1 - bx0) / (x1 - x0), (by1 - by0) / (y1 - y0))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    bcx, bcy = (bx0 + bx1) / 2, (by0 + by1) / 2

    def pt(x, y):
        tx, ty = turn((x, y), deg, SIZE[fid])
        return [round((bcx + (tx - cx) * s) * K, 1), round((bcy + (ty - cy) * s) * K, 1)]
    return pt


def inside(pt, poly):
    x, y = pt
    c = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c


SPEC = [
    ('Q', 'Quadrangle', 'Welcome Center (tickets) · the five museums · Dr. Seuss Sculpture Garden · café · parking',
     Q, Q_CLOSED, Q_DOORS, Q_AMEN, Q_LABELS),
    ('S0', 'Science · Lower Level', 'Live Animal Center & Aquarium · Connecticut River · Exploration Center · Discovery '
     'Lab', S0, S0_CLOSED, S0_DOORS, S0_AMEN, S0_LABELS),
    ('S1', 'Science · Floor 1', 'Welcome Center (tickets) · Dinosaur Hall · African Hall · Mammal Hall · Native '
     'American Hall · Store', S1, S1_CLOSED, S1_DOORS, S1_AMEN, S1_LABELS),
    ('S2', 'Science · Floor 2', 'Seymour Planetarium · SparkLab · Earth Hall · Astronomy Hall · Changing Exhibitions',
     S2, S2_CLOSED, S2_DOORS, S2_AMEN, S2_LABELS),
    ('A1', 'Smith · Floor 1', 'Japanese Arms & Armor · Italian Paintings · Plaster Casts · Changing Exhibitions',
     A1, A1_CLOSED, A1_DOORS, A1_AMEN, A1_LABELS),
    ('A2', 'Smith · Floor 2', 'American Paintings Salon · Chinese Cloisonné, Jade, Porcelain · Japanese art · Islamic '
     'World · Hasbro Games Art Discovery Center', A2, A2_CLOSED, A2_DOORS, A2_AMEN, A2_LABELS),
    ('F1', 'Fine Arts · Floor 1', 'Blake Court · American art · Modern & Contemporary · Prints', F1, F1_CLOSED,
     F1_DOORS, F1_AMEN, F1_LABELS),
    ('F2', 'Fine Arts · Floor 2', 'Impressionists · French, Italian, Dutch and Flemish art · Renaissance · Changing '
     'Exhibitions', F2, F2_CLOSED, F2_DOORS, F2_AMEN, F2_LABELS),
    ('D1', 'Seuss · Floor 1', 'Mulberry Street · Readingville · Young Ted in Springfield · Whoville', D1, D1_CLOSED,
     D1_DOORS, D1_AMEN, D1_LABELS),
    ('D2', 'Seuss · Floor 2', 'Ted, Dr. Seuss · Ted2Ted · Sal Da Who', D2, D2_CLOSED, D2_DOORS, D2_AMEN, D2_LABELS),
    ('H1', 'History · Floor 1', 'Automobiles · SIS Hall · Hasbro Gameland · Made in the Valley · Police & Fire', H1,
     H1_CLOSED, H1_DOORS, H1_AMEN, H1_LABELS),
    ('H2', 'History · Floor 2', 'Indian Motocycles · Gee Bee Aviation · Smith & Wesson · Civil War · Bicycles', H2,
     H2_CLOSED, H2_DOORS, H2_AMEN, H2_LABELS),
]


def build_floors():
    floors, seen = [], set()
    for order, (fid, label, area, rooms_in, closed_in, doors_in, amen, labels) in enumerate(SPEC):
        if fid == 'Q':
            pt = lambda x, y: [round(x * K, 1), round(y * K, 1)]
        else:
            pt = placer(fid, [r[3] for r in rooms_in] + closed_in)
        rooms = []
        for rid, kind, name, poly, short in rooms_in:
            assert rid not in seen, rid
            seen.add(rid)
            r = {'id': rid, 'kind': kind, 'name': name, 'poly': [pt(*q) for q in poly]}
            if kind == 'gallery': r['label'] = short or rid
            rooms.append(r)
        ids = {r['id'] for r in rooms}
        doors = [{'a': a, 'b': b, 'at': pt(x, y), 'width': 12, 'axis': 'o'} for a, b, (x, y) in doors_in]
        for d in doors:
            assert d['a'] in ids and d['b'] in ids, (fid, d)
        f = {'id': fid, 'label': label, 'area': area, 'order': order, 'transform': [1, 0, 0], 'rooms': rooms,
             'closed': [{'poly': [pt(*q) for q in c]} for c in closed_in],
             'amenities': [{'type': t, 'at': pt(x, y)} for t, x, y in amen],
             'labels': [{'text': t, 'kind': k, 'at': pt(x, y)} for t, k, x, y in labels],
             'doors': doors}
        if fid == 'Q':
            f['homeView'] = ['Science Museum building', 'Smith Art Museum building', "D'Amour building",
                             'Seuss building', 'History building', 'Sculpture Garden']
        for a in f['amenities']:
            assert any(inside(a['at'], r['poly']) for r in rooms), (fid, a)
        floors.append(f)
    return {'about': 'Built by tools/build_spfld.py. Traced from the Springfield Museums’ own maps '
                     '(springfieldmuseums.org/map): the Quadrangle, and every floor of the five museums with their '
                     'galleries, restrooms, elevators, stairs, information desks and entrances. The floor maps are '
                     'diagrams, not to scale: each is turned to face the way its building stands on the Quadrangle '
                     'and drawn large in the middle of the map, with walls simplified.',
            'source': 'Springfield Museums, Museum Maps (campus map 2017, floor maps 2020)',
            'units': 'pixels of the museum’s campus map (878 px wide); State Street at the top, Edwards Street at the '
                     'bottom, as on the museum’s map. Each museum’s floors are drawn large over the middle of it',
            'approximate': False, 'defaultFloor': 'Q', 'galleryWord': 'Gallery', 'floors': floors}


# ---- the works ---------------------------------------------------------------------------------------------------

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
        if im.mode in ('RGBA', 'LA', 'P'):
            im = im.convert('RGBA')
            bg = Image.new('RGB', im.size, 'white'); bg.paste(im, mask=im.split()[-1]); im = bg
        im = im.convert('RGB')
        im.thumbnail((1000, 1000))
        im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)
    return f'data/spfld/images/{key}.jpg'


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')[:60]


# gallery page (path under /about/) -> (room, kind); None = not a gallery (history, jobs...)
PAGE_ROOM = {
    'springfield-science-museum/': ('Science Welcome Center', 'Museum'),
    'springfield-science-museum/living-waters/': ('Live Animal Center', 'Gallery'),
    'springfield-science-museum/dinosaur-hall/': ('Dinosaur Hall', 'Gallery'),
    'springfield-science-museum/dinosaurs-still-live-the-story-of-archosaurs/': ('Tolman Hall', 'Exhibition'),
    'springfield-science-museum/r-e-phelon-african-hall/': ('African Hall', 'Gallery'),
    'springfield-science-museum/sparklab/': ('SparkLab', 'Gallery'),
    'springfield-science-museum/mineral-hall/': ('Earth Hall', 'Gallery'),
    'springfield-science-museum/seymour-planetarium/': ('Seymour Planetarium', 'Gallery'),
    'smith-art-museum/': ('Smith Lobby', 'Museum'),
    'smith-art-museum/japanese-arms-armor/': ('Japanese Arms & Armor', 'Gallery'),
    'smith-art-museum/the-grand-tour-george-and-belle-smith-collect-in-italy/': ('Italian Paintings', 'Gallery'),
    'smith-art-museum/plaster-cast-collection/': ('Plaster Cast Gallery', 'Gallery'),
    'smith-art-museum/tiffany-stained-glass-windows/': ('Japanese Arms & Armor', 'Feature'),
    'smith-art-museum/american-paintings-salon/': ('American Paintings Salon', 'Gallery'),
    'smith-art-museum/chinese-cloisonne/': ('Chinese Cloisonné', 'Gallery'),
    'smith-art-museum/hasbro-games-art-discovery-center/': ('Hasbro Games Art Discovery Center', 'Gallery'),
    'museum-of-fine-arts/': ('Fine Arts Lobby', 'Museum'),
    'museum-of-fine-arts/blake-court/': ('Blake Court', 'Gallery'),
    'museum-of-fine-arts/the-carol-and-noel-leary-gallery-of-impressionist-art/': ('Leary Gallery', 'Gallery'),
    'museum-of-fine-arts/19th-century-french-gallery/': ('19th-Century French', 'Gallery'),
    'museum-of-fine-arts/dutch-and-flemish-galleries/': ('17th-Century Dutch', 'Gallery'),
    'museum-of-fine-arts/the-janee-armstrong-friedmann-gallery-of-french-18th-century-art/': ('Friedmann Gallery',
                                                                                                  'Gallery'),
    'dr-seuss-museum/': ('Mulberry Street', 'Museum'),
    'dr-seuss-museum/entry-hall/': ('Mulberry Street', 'Gallery'),
    'dr-seuss-museum/readingville/': ('Readingville', 'Gallery'),
    'dr-seuss-museum/young-ted-springfield/': ('Young Ted in Springfield', 'Gallery'),
    'dr-seuss-museum/fairfield-street/': ('Fairfield Street', 'Gallery'),
    'dr-seuss-museum/whoville/': ('Whoville', 'Gallery'),
    'dr-seuss-museum/the-cats-corner/': ('Mulberry Street', 'Gallery'),
    'dr-seuss-museum/ted2ted/': ('Ted2Ted', 'Gallery'),
    'dr-seuss-museum/ted-dr-seuss/': ('Ted, Dr. Seuss', 'Gallery'),
    'dr-seuss-museum/sal-da-making-dr-seuss-sculpture-garden/': ('Sal Da Who', 'Gallery'),
    'dr-seuss-sculpture-garden/': ('Sculpture Garden', 'Gallery'),
    'museum-of-springfield-history/': ('MassMutual Hall', 'Museum'),
    'museum-of-springfield-history/automobile-gallery/': ('Automobile Gallery', 'Gallery'),
    'museum-of-springfield-history/made-in-the-valley/': ('Made in the Valley', 'Gallery'),
    'museum-of-springfield-history/hasbro-gameland/': ('Hasbro Gameland', 'Gallery'),
    'museum-of-springfield-history/smith-wesson-gallery-of-firearms-history/': ('Smith & Wesson Gallery', 'Gallery'),
    'museum-of-springfield-history/john-brown-abraham-lincoln-and-the-civil-war/': ('Civil War', 'Gallery'),
    'museum-of-springfield-history/downtown-retail-gallery/': ('Downtown Retail', 'Gallery'),
    'museum-of-springfield-history/granville-brothers-aircraft/': ('Gee Bee Aviation', 'Gallery'),
    'museum-of-springfield-history/the-esta-manthos-indian-motocycle-collection/': ('Indian Motocycle Collection',
                                                                                   'Gallery'),
    'museum-of-springfield-history/springfield-history-library-archives/': ('Police & Fire', 'Library'),
}
TITLES = {
    'springfield-science-museum/': 'Springfield Science Museum',
    'smith-art-museum/': 'George Walter Vincent Smith Art Museum',
    'museum-of-fine-arts/': 'Michele & Donald D’Amour Museum of Fine Arts',
    'dr-seuss-museum/': 'The Amazing World of Dr. Seuss Museum',
    'museum-of-springfield-history/': 'Lyman & Merrie Wood Museum of Springfield History',
}
DESC = {'smith-art-museum/': 'Explore a world of art and history at the George Walter Vincent Smith Art Museum, a '
        'beautiful Italian palazzo-style building featuring the remarkable collections of George Walter Vincent Smith '
        'and Belle Townsley Smith. Discover treasures from around the globe, including Japanese lacquer, Chinese '
        'cloisonné, ceramics, bronzes, ancient artifacts, American paintings, textiles, and more. Reopened in October '
        '2026.'}
GUESSED_PAGES = {'springfield-science-museum/dinosaurs-still-live-the-story-of-archosaurs/'}
NOTES = {
    'museum-of-springfield-history/springfield-history-library-archives/':
        'Downstairs, by the stairs in the Police & Fire gallery (the floor map shows the way down, not the room).',
    'dr-seuss-museum/the-cats-corner/': 'Downstairs from Mulberry Street (the floor map shows the stairs, not the room).',
    'smith-art-museum/tiffany-stained-glass-windows/': 'The windows are in the Japanese Arms & Armor gallery and '
                                                       'around the museum, as the museum’s page says.',
}
# current shows (Nov 2026): page slug -> (room, guessed?)
SHOWS = {
    'in-natures-studio-two-centuries-of-american-landscape-painting': ('Wheeler Gallery', False),
    'habitat': ('Quadrangle', False),
    'tara-sellios-ask-now-the-beasts': ('Changing Exhibitions (Smith)', False),
    'visions-of-the-supernatural': ('Changing Exhibitions (Smith)', True),
    'markets-foodways-and-the-essence-of-place-works-from-the-museo-de-arte-de-ponce': ('Alpert Gallery', False),
    'legacies-of-surrealism-works-from-the-museo-de-arte-de-ponce': ('Starr Gallery', False),
}
SHOW_DATES = {}
# the statues in the Sculpture Garden and on the Quadrangle (the museums' campus map places each one)
OUTDOOR = [
    ('horton-court', 'Horton Court', 'Sculpture Garden', 'Lark Grey Dimond-Cates', '2002',
     'Horton the Elephant and other characters, at the north end of the Dr. Seuss National Memorial Sculpture Garden.'),
    ('cat-in-the-hat', 'Dr. Seuss & The Cat in the Hat', 'Sculpture Garden', 'Lark Grey Dimond-Cates', '2002',
     'Theodor Geisel at his drawing board with the Cat in the Hat beside him.'),
    ('storyteller', 'The Storyteller', 'Sculpture Garden', 'Lark Grey Dimond-Cates', '2002',
     'One of the garden’s bronzes of Dr. Seuss’s characters, by the garden walk.'),
    ('grinch', 'The Grinch and Max', 'Sculpture Garden', 'Lark Grey Dimond-Cates', '',
     'The Grinch and his dog Max, one of the newer bronzes (the museums’ page shows it; the 2017 campus map doesn’t).'),
    ('lorax', 'The Lorax', 'Sculpture Garden', 'Lark Grey Dimond-Cates', '2002',
     'The Lorax, who “speaks for the trees”, at the south end of the garden.'),
    ('yertle', 'Yertle the Turtle', 'Yertle Garden', 'Lark Grey Dimond-Cates', '2002',
     'Yertle the Turtle on his stack of turtles, in its own little garden near the Museum of Fine Arts.'),
    ('puritan', 'The Puritan', 'Merrick Park', 'Augustus Saint-Gaudens', '1887',
     'Saint-Gaudens’ bronze of Deacon Samuel Chapin, one of Springfield’s founders, in Merrick Park at the north end '
     'of the Quadrangle.'),
]


def clean(txt, title):
    out = []
    for l in txt.split('\n'):
        if l == title or re.search(r'\d{4}-\d\d-\d\dT\d\d:', l): continue
        if re.match(r'^(Springfield Science Museum|G\.W\.V\. Smith Art Museum|D.Amour Museum of Fine Arts|'
                    r'Wood Museum of Springfield History|The Amazing World of Dr\. Seuss Museum|Quadrangle Green)', l):
            continue
        if re.match(r'^[A-Z][a-z]+ \d{1,2}, \d{4}–', l): continue
        if l in ('At-Home Activities', 'English', 'Español', 'Map', 'First Floor', 'Second Floor'): break
        out.append(l)
    return ' '.join(out).strip()


SKIP_PIC = re.compile(r'npr|pbs|ONLINE_cp|logo', re.I)


def build_works(floors):
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    works, seen = [], set()

    def add(a, room, guessed, note):
        fl, gname = rooms[room]
        a.update({'gallery': room, 'galleryName': gname, 'floor': fl, 'placeNote': note})
        if guessed: a['placeGuessed'] = True
        if a['id'] in seen: return
        seen.add(a['id'])
        works.append({k: v for k, v in a.items() if v not in (None, '', [])})

    gals = json.loads((CACHE / 'galleries.json').read_text())
    for g in gals:
        path = g['url'].split('/about/', 1)[-1]
        if path not in PAGE_ROOM: continue
        room, kind = PAGE_ROOM[path]
        key = 'spfld-' + slug(path.rstrip('/').replace('/', '-'))
        pic = next((u for u in g['images'] if not SKIP_PIC.search(u)), None)
        title = TITLES.get(path) or g['title']
        a = {'id': key, 'title': title, 'artist': kind, 'description': DESC.get(path) or clean(g['text'], g['title'])[:1500],
             'url': g['url'], 'image': picture(key, pic)}
        if a['image']: a['imageCredit'] = 'Springfield Museums (springfieldmuseums.org)'
        add(a, room, path in GUESSED_PAGES,
            NOTES.get(path) or ('A new exhibition the 2020 floor map doesn’t show: placing it beside Dinosaur Hall is '
                                'our guess.' if path in GUESSED_PAGES else 'Where the museum’s floor map puts it.'))
    for g in json.loads((CACHE / 'shows.json').read_text()):
        sl = g['url'].rstrip('/').rsplit('/', 1)[1]
        room, guessed = SHOWS[sl]
        key = 'spfld-show-' + slug(sl)[:40]
        title = g['text'].split('\n')[0]
        if re.search(r'\d{4}-\d\d-\d\dT', title):
            title = {'markets': 'Markets, Foodways, and the Essence of Place: Works from the Museo de Arte de Ponce'}.get(
                sl.split('-')[0], title)
        dates = re.search(r'([A-Z][a-z]+ \d{1,2}, \d{4})–([A-Z][a-z]+ \d{1,2}, \d{4})', g['text'])
        pic = next((u for u in g['images'] if not SKIP_PIC.search(u)), None)
        a = {'id': key, 'title': title, 'artist': 'Exhibition', 'date': f'{dates[1]} – {dates[2]}' if dates else None,
             'description': clean(g['text'], title)[:1500], 'url': g['url'], 'image': picture(key, pic),
             'temporary': True}
        if a['image']: a['imageCredit'] = 'Springfield Museums (springfieldmuseums.org)'
        add(a, room, guessed, 'A temporary show; the museum doesn’t say which room, so this one is our guess.'
            if guessed else 'Where the museum’s exhibition page puts it.')
    pics = {'horton-court': 'horton-court-seuss-sculpture-garden', 'grinch': 'the-grinch-and-max'}
    garden = next(g for g in gals if g['url'].endswith('/about/dr-seuss-sculpture-garden/'))
    for wid, title, room, artist, date, text in OUTDOOR:
        key = 'spfld-' + wid
        pic = next((u for u in garden['images'] if wid in pics and pics[wid] in u), None)
        a = {'id': key, 'title': title, 'artist': artist, 'date': date, 'year': int(date) if date else None,
             'type': 'Sculpture', 'description': text, 'image': picture(key, pic),
             'url': SITE + ('/about/dr-seuss-sculpture-garden/' if wid != 'puritan' else '/map/')}
        if a['image']: a['imageCredit'] = 'Springfield Museums (springfieldmuseums.org)'
        add(a, room, wid == 'grinch', 'In the Sculpture Garden; where in the garden is our guess.' if wid == 'grinch'
            else 'Where the museums’ campus map puts it.')
    items_path = CACHE / 'items.json'
    items = json.loads(items_path.read_text()) if items_path.exists() else []
    for r in items:
        m = r['meta']
        if not (m.get('On View?') or '').lower().startswith('yes'): continue
        room, guessed = place(r)
        if not room: continue
        key = 'spfld-' + slug(r['url'].rstrip('/').rsplit('/', 1)[1])
        raw = re.sub(r'\s*\(.*?\)\s*$', '', m.get('Object Creator') or '').strip()
        surname = raw.split(',')[0].strip()
        maker = ' '.join(reversed([x.strip() for x in raw.split(',')])) if raw.count(',') == 1 and \
            not re.search(r'&|Co\.|Company|After', raw) else raw
        title = re.sub(r'\s+', ' ', r['title']).strip()
        if surname and ',' in title and surname.lower() in title.rsplit(',', 1)[1].lower():
            title = title.rsplit(',', 1)[0].strip()
        date = m.get('Object Creation Date')
        yr = re.search(r'\b(1\d{3}|20\d\d)\b', date or '')
        a = {'id': key, 'title': title,
             'artist': maker or 'Unknown maker', 'date': date, 'year': int(yr[1]) if yr else None,
             'medium': m.get('Medium'), 'dimensions': m.get('Dimensions'), 'creditLine': m.get('Credit'),
             'accession': m.get('Accession Number'), 'description': (r.get('text') or '')[:1500], 'url': r['url'],
             'image': picture(key, r.get('image'))}
        if a['image']: a['imageCredit'] = 'Image courtesy of the Springfield Museums'
        add(a, room, guessed, 'The museum marks it “On View”; the gallery is our guess from its subject.' if guessed
            else 'The museum marks it “On View”, in the gallery for its kind.')
    order = {r['id']: i for f in floors['floors'] for i, r in enumerate(f['rooms'])}
    forder = {f['id']: f['order'] for f in floors['floors']}
    works.sort(key=lambda a: (forder[a['floor']], order[a['gallery']],
                              a['artist'] not in ('Museum', 'Gallery', 'Exhibition', 'Feature')))
    return {'source': 'Springfield Museums: gallery, exhibition and collection pages, and museum maps '
                      '(springfieldmuseums.org)', 'checked': time.strftime('%Y-%m-%d'), 'count': len(works),
            'complete': False, 'artworks': works}


# the gallery names the museums give on a highlight's page -> rooms on the map (exact)
NAMED = {'Japanese Decorative Arts Gallery': 'Japanese Decorative Arts', 'American Paintings Salon':
         'American Paintings Salon', 'Japanese Arms and Armor Gallery': 'Japanese Arms & Armor',
         'Islamic Art Gallery': 'Islamic World', 'Japanese Bronze Gallery': 'Japanese Bronzes',
         'Astronomy Hall': 'Astronomy Hall', 'Tolman Fossil Cases': 'Tolman Hall', 'Elevator Lobby': 'Science Hall 1'}
# highlights that name only the museum: (word in the title, room), first match wins; the room is our guess
GUESS = [
    ('Rehearsal Before the Ballet', 'Leary Gallery'), ('Grainstack', 'Leary Gallery'),
    ('Bouguereau', '19th-Century French'), ('Bol', '17th-Century Dutch'),
    ('Retable', 'Northern Renaissance'), ('Triptych', 'Northern Renaissance'),
    ('Nadelman', 'Early 20th-Century American'), ('Sheeler', 'Early 20th-Century American'),
    ('O’Keeffe', 'Early 20th-Century American'), ('Feininger', '20th-Century European'),
    ('Currier', 'Print Gallery'), ('The Leaders', 'Print Gallery'), ('King of the Turf', 'Print Gallery'),
    ('Gifford', '19th-Century American'), ('Roesen', '19th-Century American'), ('Whittredge', '19th-Century American'),
    ('Inness', '19th-Century American'), ('Church', '19th-Century American'),
    ('Fire', 'Police & Fire'), ('Garand', 'Smith & Wesson Gallery'), ('Revolver', 'Smith & Wesson Gallery'),
    ('Indian', 'Indian Motocycle Collection'), ('Rolls-Royce', 'Automobile Gallery'), ('Knox', 'Automobile Gallery'),
    ('Bicycle', 'Early Bicycles'), ('Civil War', 'Civil War'), ('Bottume', 'MassMutual Hall'),
    ('Kibbe', 'Made in the Valley'), ('Westinghouse', 'Made in the Valley'), ('Victrola', 'Made in the Valley'),
    ('Telegraphone', 'Science Hall 1'),
]


def place(r):
    """Gallery for a collection highlight marked On View: (room, guessed?)."""
    parts = [p.strip() for p in r.get('museum', '').split('»')]
    if parts[-1] in NAMED: return NAMED[parts[-1]], False
    if not r.get('museum'): return None, True
    for word, room in GUESS:
        if word.lower() in r['title'].lower(): return room, True
    return None, True


def build_guide(works):
    rows = []
    for a in works['artworks']:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a['artist'], 'date': a.get('date'),
                     'year': a.get('year'), 'medium': a.get('medium'), 'accession': a.get('accession'),
                     'url': a['url'], 'imageUrl': a.get('image'), 'onView': True, 'gallery': a['gallery'],
                     'floor': a['floor']}.items() if v not in (None, '')})
    return {'museum': MUSEUM, 'name': NAME, 'checked': time.strftime('%Y-%m-%d'), 'source': works['source'],
            'onViewKnown': True,
            'note': 'Five museums on one Quadrangle, with one ticket: the Springfield Science Museum, the George Walter '
                    'Vincent Smith Art Museum, the Michele & Donald D’Amour Museum of Fine Arts, the Amazing World of '
                    'Dr. Seuss and the Lyman & Merrie Wood Museum of Springfield History. Their collections hold over '
                    '250,000 objects; listed here are the galleries, the current shows, the sculptures outside and '
                    'the collection highlights the museums mark “On View”.',
            'works': rows}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    floors = build_floors()
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    works = build_works(floors)
    (OUT / 'artworks.json').write_text(json.dumps(works, ensure_ascii=False, separators=(',', ':')))
    guide = build_guide(works)
    (ROOT / 'data' / 'guides' / f'{MUSEUM}.json').write_text(json.dumps(guide, ensure_ascii=False, separators=(',', ':')))
    idx_path = ROOT / 'data' / 'guides.json'
    idx = json.loads(idx_path.read_text())
    idx['museums'][MUSEUM] = {'works': len(guide['works']), 'pictures': sum(bool(w.get('imageUrl')) for w in guide['works']),
                              'onView': len(guide['works']), 'galleries': True,
                              'checked': guide['checked'], 'source': guide['source']}
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    by = {}
    for a in works['artworks']: by[a['gallery']] = by.get(a['gallery'], 0) + 1
    print(f'{len(floors["floors"])} floors; {works["count"]} works ({sum("image" in a for a in works["artworks"])} '
          f'with pictures)')
    for k, v in by.items(): print(f'  {k}: {v}')


if __name__ == '__main__':
    sys.exit(main())
