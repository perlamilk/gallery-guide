#!/usr/bin/env python3
"""Build the Yale Peabody Museum map guide (run: python3 tools/harvest_ypm.py, then this).

    data/ypm/floors.json       Floors 1, 2 and 3, seen from above (flat 2D)
    data/ypm/artworks.json     the galleries and the specimens and objects the museum shows on its gallery pages
    data/ypm/images/           pictures from peabody.yale.edu, made smaller for phones
    data/guides/Q122945.json   the same, for the museum page

Where the information comes from
--------------------------------
The map is traced from the museum's own floor plan ("floorplan-oct2025-web", dated 3 Oct 2025, the "Download Map
(PDF)" link on peabody.yale.edu/visit, cached in .cache/ypm/map.pdf). It has one page per floor, all drawn on the same
frame (the elevators and stairs line up), with galleries, restrooms, the all-gender restroom, elevators, stairs,
information desk, coatroom, lockers, store, classrooms and staff-only areas. Coordinates are pixels of the pages
rendered at 110 dpi, times 2 (Floor 3 is drawn 10 px further right on its page, so it is moved back). Walls are
simplified to straight lines. Whitney Avenue is at the bottom, Sachem Street on the left. The only parts that are
guesses: where Indigenous Connections ends and Mesoamerican & Andean Civilizations begins (one open room on the
plan), and which room the temporary shows are in. The wellness/lactation room is on the lower level, which the plan
doesn't draw.

The galleries and things in them: every page under peabody.yale.edu/explore/exhibitions (tools/harvest_ypm.py).
Each gallery page names the gallery (its room on the plan) and shows cards: a heading, a short text, a photo (most
by Andy Melien / Yale Peabody Museum) and often the catalogue number. Temporary shows that have ended are left out.
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
OUT = ROOT / 'data' / 'ypm'
CACHE = ROOT / '.cache' / 'ypm'
MUSEUM = 'Q122945'
NAME = 'Yale Peabody Museum'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
DX = {'1': 0, '2': 0, '3': -10}        # Floor 3 is drawn 10 px further right on its page


def P(x, y):
    return [round(x * 2, 1), round(y * 2, 1)]


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


NE_HALL = [(710, 338), (745, 338), (745, 287), (833, 287), (833, 375), (797, 375), (797, 578), (710, 578)]

# ---- Floor 1 ---------------------------------------------------------------------------------------------------
# rooms: (id, kind, name, polygon, short label for galleries)
F1 = [
    ('Lobby', 'space', 'Lobby: information desk, lockers, coatroom; wheelchairs, stools and sensory bags at the desk. '
     'The Pteranodon family flies overhead',
     [(145, 742), (300, 742), (300, 955), (262, 968), (218, 968), (180, 935), (180, 907), (117, 907), (117, 847),
      (165, 847), (165, 797), (145, 797)], None),
    ('Coatroom', 'space', 'Coatroom', rect(70, 847, 117, 907), None),
    ('Extended Lobby', 'corridor', 'Extended Lobby (group entrance from Sachem Street): overview cases of the '
     'collections', [(225, 415), (282, 412), (290, 540), (300, 540), (300, 742), (140, 742), (140, 702), (248, 698),
                     (240, 601), (237, 467)], 'Extended Lobby'),
    ('Museum Store', 'space', 'Museum Store', [(132, 607), (240, 601), (248, 697), (138, 702)], None),
    ('Restrooms 1', 'space', 'Restrooms, including an all-gender restroom', [(282, 412), (363, 405), (373, 537), (290, 540)],
     None),
    ('Richard Study Gallery', 'gallery', 'Alison F. Richard Study Gallery', [(462, 400), (592, 392), (597, 522), (472, 532)],
     'Study'),
    ('Student Gallery', 'gallery', 'Student Gallery', [(592, 392), (710, 384), (710, 515), (597, 522)], 'Student'),
    ('Central Gallery', 'gallery', 'Central Gallery: Archelon and Tylosaurus overhead, living plants and Botany. You may '
     'have a snack here', [(290, 540), (373, 537), (710, 515), (710, 578), (660, 585), (660, 650), (300, 650)],
     'Central Gallery'),
    ('North Hall 1', 'corridor', 'Stairs and elevator (north)', NE_HALL, None),
    ('Burke Hall: Life Among Dinosaurs', 'gallery', 'Burke Hall of Dinosaurs: Life Among Dinosaurs and Ancient Oceans, '
     'under The Age of Reptiles mural', rect(300, 650, 677, 812), 'Dinosaurs'),
    ('The Human Footprint', 'gallery', 'The Human Footprint', rect(300, 812, 677, 942), 'Human Footprint'),
    ('A World of Change', 'gallery', 'A World of Change: life after the dinosaurs, the age of mammals',
     [(677, 650), (797, 650), (797, 758), (847, 758), (847, 808), (797, 808), (797, 942), (677, 942)], 'World of Change'),
]
F1_CLOSED = [[(122, 475), (237, 467), (240, 601), (132, 607)], [(363, 405), (462, 400), (472, 532), (373, 537)],
             [(660, 585), (797, 578), (797, 650), (660, 650)], rect(300, 942, 417, 1022)]
F1_DOORS = [('Lobby', 'Burke Hall: Life Among Dinosaurs', (300, 775)), ('Lobby', 'The Human Footprint', (300, 860)),
            ('Lobby', 'Coatroom', (117, 870)), ('Lobby', 'Extended Lobby', (250, 742)),
            ('Extended Lobby', 'Museum Store', (244, 650)), ('Extended Lobby', 'Restrooms 1', (286, 475)),
            ('Extended Lobby', 'Central Gallery', (295, 600)), ('Central Gallery', 'Richard Study Gallery', (530, 527)),
            ('Central Gallery', 'Student Gallery', (650, 519)), ('Central Gallery', 'Burke Hall: Life Among Dinosaurs', (380, 650)),
            ('Central Gallery', 'Burke Hall: Life Among Dinosaurs', (580, 650)), ('Central Gallery', 'North Hall 1', (710, 550)),
            ('Burke Hall: Life Among Dinosaurs', 'A World of Change', (677, 700)), ('The Human Footprint', 'A World of Change', (677, 880))]
F1_AMEN = [('entrance', 240, 958), ('entrance', 155, 722), ('info', 240, 880), ('coat', 93, 877), ('stairs', 150, 892),
           ('elevator', 170, 770), ('shop', 190, 650), ('restroom', 335, 440), ('restroom-all', 312, 515),
           ('stairs', 771, 445), ('elevator', 771, 312), ('elevator', 822, 783)]
F1_LABELS = [('WHITNEY AVENUE (main entrance) ↓', 260, 1060), ('Sachem St ←', 85, 760),
             ('Bass Court', 845, 560)]
F1_NOTES = [('Lockers', 205, 820), ('Classroom', 180, 540), ('Classroom', 418, 470), ('Classroom', 358, 985),
            ('The Age of Reptiles mural', 490, 803), ('Botany', 605, 622)]

# ---- Floor 2 ---------------------------------------------------------------------------------------------------
F2 = [
    ('Special Exhibitions', 'gallery', 'Special Exhibitions (the temporary gallery)', [(122, 473), (227, 465), (242, 742),
                                                                                    (136, 742)], 'Special'),
    ('Mural Overlook', 'corridor', 'Mural Overlook: look down on Burke Hall and The Age of Reptiles mural',
     [(225, 415), (282, 412), (290, 548), (300, 650), (300, 812), (250, 812), (245, 742), (227, 465)], None),
    ('West Stairs 2', 'corridor', 'Stairs and elevator (west)',
     [(145, 742), (245, 742), (250, 812), (200, 842), (187, 842), (187, 902), (70, 902), (70, 842), (160, 842),
      (160, 795), (145, 795)], None),
    ('Rotunda 2', 'corridor', 'Rotunda, open to the Lobby below',
     [(215, 812), (285, 812), (300, 827), (300, 907), (285, 922), (215, 922), (200, 907), (200, 842)], None),
    ('Restrooms 2', 'space', 'Restrooms', [(282, 412), (363, 405), (368, 460), (290, 465)], None),
    ('North Balcony', 'corridor', 'Balcony over the Central Gallery (seats)',
     [(290, 465), (368, 460), (710, 450), (710, 515), (662, 518), (290, 548)], None),
    ('Rest Space 2', 'space', 'Rest Space', [(662, 518), (710, 515), (710, 585), (662, 585)], None),
    ('North Hall 2', 'corridor', 'Stairs and elevator (north)',
     [(710, 338), (745, 338), (745, 287), (833, 287), (833, 375), (797, 375), (797, 515), (745, 515), (745, 605),
      (797, 605), (797, 650), (710, 650)], None),
    ('History of Science and Technology', 'gallery', 'History of Science and Technology',
     [(300, 812), (417, 812), (417, 890), (470, 906), (470, 942), (417, 942), (417, 1022), (300, 1022)], 'Science & Tech'),
    ('Ancient Egypt and Mesopotamia', 'gallery', 'Ancient Egypt and Mesopotamia (funerary items on display)',
     [(417, 812), (677, 812), (677, 942), (470, 942), (470, 906), (417, 890)], 'Egypt'),
    ('Indigenous Connections', 'gallery', 'Indigenous Connections (where it ends and the next gallery begins is '
     'approximate)', [(677, 650), (797, 650), (797, 758), (847, 758), (847, 808), (797, 808), (797, 790), (677, 790)],
     'Indigenous'),
    ('Mesoamerican and Andean Civilizations', 'gallery', 'Mesoamerican and Andean Civilizations (funerary items on '
     'display)', rect(677, 790, 797, 942), 'Americas'),
]
F2_CLOSED = [[(290, 548), (662, 518), (662, 650), (300, 650)], rect(300, 650, 677, 812),
             [(363, 405), (710, 382), (710, 450), (368, 460)], [(662, 585), (710, 585), (710, 650), (662, 650)]]
F2_DOORS = [('Mural Overlook', 'Special Exhibitions', (234, 600)), ('Mural Overlook', 'Restrooms 2', (286, 440)),
            ('Mural Overlook', 'North Balcony', (289, 505)), ('North Balcony', 'North Hall 2', (710, 480)),
            ('Rest Space 2', 'North Hall 2', (710, 550)), ('North Balcony', 'Rest Space 2', (686, 517)),
            ('Mural Overlook', 'West Stairs 2', (247, 775)), ('Mural Overlook', 'Rotunda 2', (265, 812)),
            ('Rotunda 2', 'West Stairs 2', (194, 870)), ('Rotunda 2', 'History of Science and Technology', (300, 860)),
            ('History of Science and Technology', 'Ancient Egypt and Mesopotamia', (417, 850)),
            ('Ancient Egypt and Mesopotamia', 'Mesoamerican and Andean Civilizations', (677, 880)),
            ('Mesoamerican and Andean Civilizations', 'Indigenous Connections', (737, 790)),
            ('Indigenous Connections', 'North Hall 2', (750, 650))]
F2_AMEN = [('restroom', 325, 435), ('elevator', 771, 312), ('stairs', 771, 445), ('elevator', 822, 783),
           ('elevator', 170, 768), ('stairs', 120, 872)]
F2_LABELS = [('Open to the Central Gallery below', 480, 590), ('Open to Burke Hall below', 490, 735)]
F2_NOTES = [('Classroom 221', 790, 538), ('The Age of Reptiles mural', 490, 803)]

# ---- Floor 3 (page coordinates; moved by DX) ---------------------------------------------------------------------
F3 = [
    ('West Hall 3', 'corridor', 'Hallway', [(235, 415), (295, 410), (298, 548), (250, 548), (244, 518)], None),
    ('Restrooms 3', 'space', 'Restrooms, including an all-gender restroom', [(295, 410), (373, 405), (380, 500),
                                                                             (297, 503)], None),
    ('Hall of the Pacific', 'gallery', 'Hall of the Pacific',
     [(373, 405), (720, 382), (720, 515), (683, 515), (330, 548), (298, 548), (297, 503), (380, 500)], 'Pacific'),
    ('David Friend Hall', 'gallery', 'David Friend Hall: minerals and gems (Minerals, Earth and Space)',
     [(132, 473), (240, 465), (250, 683), (143, 683)], 'David Friend Hall'),
    ('Minerals, Earth and Space', 'gallery', 'Minerals, Earth and Space', [(250, 548), (330, 548), (333, 668),
                                                                         (258, 672)], 'Minerals'),
    ('Minerals, Earth and Space (south)', 'gallery', 'Minerals, Earth and Space: Earth and space',
     [(143, 683), (258, 672), (270, 845), (205, 845), (205, 740), (147, 740)], 'Earth & Space'),
    ('West Stairs 3', 'corridor', 'Stairs and elevator (west)',
     [(147, 740), (205, 740), (205, 845), (270, 845), (270, 918), (215, 918), (215, 902), (80, 902), (80, 842),
      (175, 842), (175, 795), (147, 795)], None),
    ('North American Dioramas', 'gallery', 'North American Dioramas', rect(270, 812, 388, 1022), 'North America'),
    ('Dynamic Nature', 'gallery', 'Dynamic Nature', rect(388, 812, 695, 942), 'Dynamic Nature'),
    ('Connecticut Dioramas', 'gallery', 'Connecticut Dioramas', rect(695, 812, 805, 942), 'Connecticut'),
    ('Living Lab', 'gallery', 'Living Lab: live animals and things you can touch',
     [(697, 690), (805, 690), (805, 758), (857, 758), (857, 808), (805, 808), (805, 812), (697, 812)], 'Living Lab'),
    ('Rest Space 3', 'space', 'Rest Space', [(683, 515), (720, 515), (720, 585), (683, 585)], None),
    ('North Hall 3', 'corridor', 'Stairs and elevator (north)',
     [(720, 338), (755, 338), (755, 287), (843, 287), (843, 375), (805, 375), (805, 515), (755, 515), (755, 690),
      (720, 690)], None),
]
F3_CLOSED = [[(330, 548), (683, 520), (683, 650), (333, 650)],
             [(333, 650), (697, 650), (697, 812), (270, 812), (265, 740), (258, 672), (333, 668)],
             [(683, 585), (720, 585), (720, 690), (697, 690), (697, 650), (683, 650)],
             rect(755, 515, 857, 690)]
F3_DOORS = [('West Hall 3', 'Hall of the Pacific', (297, 525)), ('West Hall 3', 'David Friend Hall', (242, 495)),
            ('West Hall 3', 'Minerals, Earth and Space', (275, 548)), ('David Friend Hall', 'Minerals, Earth and Space', (252, 610)),
            ('David Friend Hall', 'Minerals, Earth and Space (south)', (200, 683)),
            ('Minerals, Earth and Space (south)', 'West Stairs 3', (238, 845)), ('West Stairs 3', 'North American Dioramas', (270, 880)),
            ('North American Dioramas', 'Dynamic Nature', (388, 880)), ('Dynamic Nature', 'Connecticut Dioramas', (695, 880)),
            ('Connecticut Dioramas', 'Living Lab', (740, 812)), ('Living Lab', 'North Hall 3', (738, 690)),
            ('Hall of the Pacific', 'North Hall 3', (720, 450)), ('Rest Space 3', 'North Hall 3', (720, 550)),
            ('Hall of the Pacific', 'Rest Space 3', (700, 516)), ('West Hall 3', 'Restrooms 3', (296, 470))]
F3_AMEN = [('restroom-all', 312, 432), ('restroom', 345, 460), ('elevator', 780, 312), ('stairs', 780, 445),
           ('elevator', 832, 783), ('elevator', 180, 767), ('stairs', 130, 872)]
F3_LABELS = [('Open to the Central Gallery below', 505, 595)]
F3_NOTES = []

LABEL_AT = {}


def inside(pt, poly):
    x, y = pt
    c = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c


def floor(fid, label, order, area, rooms, closed, doors, amen, labels, notes):
    dx = DX[fid]
    mv = lambda q: P(q[0] + dx, q[1])
    rr = []
    for rid, kind, name, poly, short in rooms:
        r = {'id': rid, 'kind': kind, 'name': name, 'poly': [mv(q) for q in poly]}
        if kind == 'gallery': r['label'] = short
        if rid in LABEL_AT: r['labelAt'] = mv(LABEL_AT[rid])
        rr.append(r)
    return {'id': fid, 'label': label, 'order': order, 'transform': [0.25, 0, 0], 'area': area, 'rooms': rr,
            'closed': [{'poly': [mv(q) for q in c]} for c in closed],
            'amenities': [{'type': t, 'at': mv((x, y))} for t, x, y in amen],
            'labels': [{'text': t, 'kind': 'area', 'at': mv((x, y))} for t, x, y in labels],
            'notes': [{'text': t, 'kind': 'note', 'at': mv((x, y))} for t, x, y in notes],
            'doors': [{'a': a, 'b': b, 'at': mv(p), 'width': 16, 'axis': 'o'} for a, b, p in doors]}


def build_floors():
    floors = [
        floor('1', 'Floor 1', 0, 'Entrance, information · Dinosaurs · Human Footprint · World of Change · Central '
              'Gallery · Store', F1, F1_CLOSED, F1_DOORS, F1_AMEN, F1_LABELS, F1_NOTES),
        floor('2', 'Floor 2', 1, 'Special Exhibitions · Egypt & Mesopotamia · Mesoamerica & Andes · Science & '
              'Technology · Mural Overlook', F2, F2_CLOSED, F2_DOORS, F2_AMEN, F2_LABELS, F2_NOTES),
        floor('3', 'Floor 3', 2, 'Minerals, Earth & Space · Dioramas · Dynamic Nature · Living Lab · Hall of the '
              'Pacific', F3, F3_CLOSED, F3_DOORS, F3_AMEN, F3_LABELS, F3_NOTES),
    ]
    for f in floors:
        ids = [r['id'] for r in f['rooms']]
        assert len(ids) == len(set(ids)), f['id']
        for d in f['doors']:
            assert d['a'] in ids and d['b'] in ids, (f['id'], d)
        for a in f['amenities']:
            assert any(inside(a['at'], r['poly']) for r in f['rooms']), (f['id'], a)
    return {'about': 'Built by tools/build_ypm.py. Traced from the Yale Peabody Museum’s own floor plan (October 2025, '
                     '“Download Map” on peabody.yale.edu/visit): the three floors, galleries, restrooms, elevators, '
                     'stairs, information desk, coatroom, lockers and store where the museum puts them. Walls are '
                     'simplified. The wellness/lactation room is on the lower level, which the plan does not show.',
            'source': 'Yale Peabody Museum, floor plan (3 Oct 2025)',
            'units': 'pixels of the museum’s floor plan pages (110 dpi) x 2; Whitney Avenue is at the bottom',
            'approximate': False, 'defaultFloor': '1', 'galleryWord': 'Gallery', 'floors': floors}


# ---- galleries and objects ---------------------------------------------------------------------------------------

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
    return f'data/ypm/images/{key}.jpg'


# gallery page -> room on the plan
PAGE_ROOM = {
    'lobby': 'Lobby', 'extended-lobby': 'Extended Lobby', 'central-gallery': 'Central Gallery',
    'burke-hall-dinosaurs': 'Burke Hall: Life Among Dinosaurs', 'burke-hall-ancient-oceans': 'Burke Hall: Life Among Dinosaurs',
    'world-of-change': 'A World of Change', 'human-footprint': 'The Human Footprint',
    'richard-study-gallery': 'Richard Study Gallery', 'student-gallery': 'Student Gallery',
    'history-science-technology': 'History of Science and Technology',
    'ancient-egypt-mesopotamia': 'Ancient Egypt and Mesopotamia', 'mesoamerica-andes': 'Mesoamerican and Andean Civilizations',
    'minerals-earth-space': 'David Friend Hall', 'north-american-dioramas': 'North American Dioramas',
    'dynamic-nature': 'Dynamic Nature', 'connecticut-dioramas': 'Connecticut Dioramas', 'living-lab': 'Living Lab',
    'hall-of-the-pacific': 'Hall of the Pacific',
}
# Cards for shows that have ended (the Student Gallery page also lists its past shows)
PAST = {'Of All Wild Things', 'Fakes and Fictions? Unraveling Museum Narratives'}
# Temporary shows on view (Nov 2026): title -> (room, placed by guess?)
TEMP = {
    'About Time': ('Special Exhibitions', True),
    'Unfolding History': ('Special Exhibitions', True),
    'Soft Traces': ('Special Exhibitions', True),
    'Picturing at the Peabody': ('Special Exhibitions', True),
    'The Rocks Cry Out': ('Special Exhibitions', True),
    'There Are No Horses on Horse Island': ('Special Exhibitions', True),
}
# Cards whose room is more exact than the page's
CARD_ROOM = {('minerals-earth-space', 'Quartz Sandstone Concretion'): None}
EXTRA = [
    ('stegosaurus', 'Burke Hall: Life Among Dinosaurs', 'Stegosaurus', 'Fossil',
     'One of the two big dinosaurs in the middle of Burke Hall, next to the Brontosaurus (the museum’s page for the '
     'hall names both).', 'burke-hall-dinosaurs'),
]


def kind_of(r, room):
    if r['kind'] == 'gallery': return 'Gallery'
    if r['page'] == 'temporary-exhibitions' or r['page'] == 'student-gallery': return 'Exhibition'
    if r['page'] == 'richard-study-gallery': return 'Course display'
    return 'Object'


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')[:60]


def build_works(floors):
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    p = CACHE / 'cards.json'
    if not p.exists(): raise SystemExit('run tools/harvest_ypm.py first')
    rows = json.loads(p.read_text())
    works, seen = [], set()

    def add(a, room, guessed, note):
        fl, gname = rooms[room]
        a.update({'gallery': room, 'galleryName': gname, 'floor': fl, 'placeNote': note})
        if guessed: a['placeGuessed'] = True
        works.append({k: v for k, v in a.items() if v not in (None, '', [])})

    hero = {}
    for r in rows:
        page = r['page']
        if page == 'temporary-exhibitions':
            if r['kind'] == 'gallery' or r['title'] not in TEMP: continue
            room, guessed = TEMP[r['title']]
        else:
            if r['title'] in PAST: continue
            room, guessed = PAGE_ROOM[page], False
        key = f"ypm-{slug(page)}" if r['kind'] == 'gallery' else f"ypm-{slug(r['title'])}"
        if key in seen: continue
        seen.add(key)
        desc = r['text'].replace('\n', ' ')
        a = {'id': key, 'title': r['title'], 'artist': kind_of(r, room), 'description': desc[:1500],
             'url': r.get('url') or f'https://peabody.yale.edu/explore/exhibitions/{page}',
             'image': picture(key, r['image'])}
        if r.get('catalog'): a['accession'] = ', '.join(c for c in r['catalog'] if c.startswith('YPM') or c.startswith('YU'))
        if a['image']:
            cr = r.get('credit') or ''
            a['imageCredit'] = cr.replace('Photo credit:', 'Photo:').replace('Photo Credit:', 'Photo:') \
                if 'credit' in cr.lower() or 'courtesy' in cr.lower() else 'Yale Peabody Museum (peabody.yale.edu)'
        if r['kind'] == 'gallery': hero[page] = a['image']
        if room == 'Special Exhibitions' or page == 'student-gallery': a['temporary'] = True
        if guessed:
            note = 'A temporary show; the museum doesn’t say which room, so placing it in the Special Exhibitions ' \
                   'gallery (the second-floor temporary gallery) is our guess.'
        elif page == 'burke-hall-ancient-oceans':
            note = 'Burke Hall, on the museum’s floor plan (Ancient Oceans is part of the hall).'
        else:
            note = 'Where the museum’s floor plan and gallery page put it.'
        add(a, room, guessed, note)
    for key, room, title, kind, text, pic_page in EXTRA:
        a = {'id': f'ypm-{key}', 'title': title, 'artist': kind, 'description': text,
             'url': f'https://peabody.yale.edu/explore/exhibitions/{pic_page}', 'image': hero.get(pic_page)}
        if a['image']: a['imageCredit'] = 'Yale Peabody Museum (peabody.yale.edu): photo of the hall'
        add(a, room, False, 'Where the museum’s gallery page puts it.')
    order = {r['id']: i for f in floors['floors'] for i, r in enumerate(f['rooms'])}
    forder = {f['id']: f['order'] for f in floors['floors']}
    works.sort(key=lambda a: (forder[a['floor']], order[a['gallery']], a['artist'] != 'Gallery'))
    return {'source': 'Yale Peabody Museum: exhibition pages and floor plan (peabody.yale.edu)',
            'checked': time.strftime('%Y-%m-%d'), 'count': len(works), 'complete': False, 'artworks': works}


def build_guide(works):
    rows = []
    for a in works['artworks']:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a['artist'],
                     'medium': a.get('accession'), 'url': a['url'], 'imageUrl': a.get('image'), 'onView': True,
                     'gallery': a['gallery'], 'floor': a['floor']}.items() if v not in (None, '')})
    return {'museum': MUSEUM, 'name': NAME, 'checked': time.strftime('%Y-%m-%d'),
            'source': 'Yale Peabody Museum: exhibition pages and floor plan (peabody.yale.edu)', 'onViewKnown': True,
            'note': 'The Peabody’s collections hold about 14 million specimens and objects; only a small part is on '
                    'view. Its online database can’t be read by this guide, so listed here are the galleries and the '
                    'specimens and objects the museum features on its gallery pages, in the rooms where its floor plan '
                    'puts them.',
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
    print(f'{works["count"]} galleries and objects ({sum("image" in a for a in works["artworks"])} with pictures)')
    for k, v in by.items(): print(f'  {k}: {v}')


if __name__ == '__main__':
    sys.exit(main())
