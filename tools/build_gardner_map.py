#!/usr/bin/env python3
"""Build the Isabella Stewart Gardner Museum map guide (run: python3 tools/build_gardner_map.py).

    data/gardner/floors.json    three floors seen from above (a flat 2D plan): the Palace and the New Wing
    data/gardner/artworks.json  works from data/guides/Q49135.json (Wikidata, CC0) placed in their room

The map: the museum's own visitor map (gardnermuseum.org, "ISGM_Map_English 9.30.26.pdf", pages 4 and 5)
draws each floor flat, with straight walls. The rooms below are those walls' coordinates in PDF points,
read off the PDF's vector drawing; doors are the gaps in the walls. The Palace sits to the right of the
New Wing, joined on the first floor by the glass walkway (the only way between the two buildings), so
Palace points are shifted by PALACE_SHIFT to line up with the New Wing in one frame, and each Palace floor
by its own extra shift so the stairs and elevator sit in the same place on every floor.

The works: Isabella placed every object herself and her will forbids moving them, so each work stays in one
room. The museum's object numbers say which: "P21w27" is a painting (P) in room 21 (the Dutch Room), on the
west wall, place 27. ROOM_CODES maps those numbers to rooms; the codes were matched with the works the
visitor map shows in each room. Numbers not listed (and drawings, books and archive items, whose numbers
look different) aren't placed on the map, and still show on the museum page.
"""
import json
import re
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'gardner'
MUSEUM = 'Q49135'
SOURCE = 'https://www.gardnermuseum.org/sites/default/files/2025-10/ISGM_Map_English%209.30.26.pdf'

PALACE_SHIFT = (260, 2)                      # page 5 (Palace) -> page 4 (New Wing) frame
LEVEL_SHIFT = {'1': 0, '2': 211, '3': 368}   # Palace floors 2 and 3 are drawn higher up the page
WING2_SHIFT = 215                            # New Wing floor 2 is drawn above floor 1 on page 4


def rect(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


# (id, kind, name, polygon) in each page's own PDF points.
# kind: gallery = a room with art (shows its count), space = a named room, corridor = a way through.
PALACE = {
    '1': [
        ('Courtyard', 'gallery', 'Courtyard', rect(120, 446, 234, 537)),
        ('Cloisters', 'gallery', 'Cloisters',
         [[234, 431], [254, 431], [254, 556], [55, 556], [55, 535], [120, 535], [120, 537], [234, 537]]),
        ('Rear Hall', 'gallery', 'Rear Hall · Worthington Street Lobby',
         [[95, 431], [234, 431], [234, 446], [120, 446], [120, 535], [95, 535]]),
        ('1-restrooms', 'space', 'Restrooms', rect(55, 458, 95, 510)),
        ('Spanish Cloister', 'gallery', 'Spanish Cloister', rect(120, 556, 254, 585)),
        ('Chinese Loggia', 'gallery', 'Chinese Loggia', rect(120, 585, 234, 602)),
        ('Spanish Chapel', 'gallery', 'Spanish Chapel', rect(234, 585, 254, 602)),
        ('Macknight Room', 'gallery', 'Macknight Room', rect(254, 431, 300, 472)),
        ('Vatichino', 'gallery', 'Vatichino', rect(254, 472, 300, 486)),
        ('Blue Room', 'gallery', 'Blue Room', rect(254, 486, 300, 556)),
        ('Fenway Gallery', 'space', 'Fenway Gallery · Special exhibitions', rect(254, 556, 300, 579)),
        ('Yellow Room', 'gallery', 'Yellow Room', rect(254, 579, 300, 602)),
    ],
    '2': [
        ('Second Floor Stairhall', 'gallery', 'Second Floor Stairhall', rect(119, 220, 233, 245)),
        ('2-courtyard', 'space', 'Courtyard below', rect(119, 245, 233, 323)),
        ('Early Italian Room', 'gallery', 'Early Italian Room', rect(233, 220, 300, 260)),
        ('Raphael Room', 'gallery', 'Raphael Room', rect(233, 260, 300, 323)),
        ('Short Gallery', 'gallery', 'Short Gallery', rect(233, 323, 300, 347)),
        ('Little Salon', 'gallery', 'Little Salon', rect(233, 347, 300, 392)),
        ('Dutch Room', 'gallery', 'Dutch Room', rect(55, 220, 119, 303)),
        ('Second Floor Passage', 'gallery', 'Second Floor Passage', rect(55, 303, 119, 323)),
        ('Tapestry Room', 'gallery', 'Tapestry Room', rect(55, 323, 233, 392)),
    ],
    '3': [
        ('Third Floor Stairhall', 'gallery', 'Third Floor Stairhall', rect(120, 63, 234, 87)),
        ('3-courtyard', 'space', 'Courtyard below', rect(120, 87, 234, 162)),
        ('Veronese Room', 'gallery', 'Veronese Room', rect(234, 63, 299, 104)),
        ('Titian Room', 'gallery', 'Titian Room', rect(234, 104, 299, 163)),
        ('Long Gallery', 'gallery', 'Long Gallery', [[120, 162], [234, 162], [234, 163], [299, 163], [299, 185], [120, 185]]),
        ('Chapel', 'gallery', 'Chapel',
         [[55, 163], [120, 163], [120, 185], [89, 185], [89, 196], [76, 196], [76, 185], [55, 185]]),
        ('Gothic Room', 'gallery', 'Gothic Room', rect(55, 63, 120, 143)),
        ('Third Floor Passage', 'gallery', 'Third Floor Passage', rect(55, 143, 120, 163)),
    ],
}

# The New Wing (page 4), already in the shared frame on floor 1.
WING = {
    '1': [
        ('Tickets', 'space', 'Tickets', rect(46, 654, 129, 691)),
        ('1-entrance-hall', 'corridor', 'Entrance hall',
         [[125, 574], [200, 574], [200, 630], [185, 630], [185, 691], [129, 691], [129, 654], [125, 654]]),
        ('Store', 'space', 'Store', rect(79, 589, 125, 630)),
        ('Living Room', 'space', 'Living Room', rect(200, 574, 241, 630)),
        ('Studio', 'space', 'Studio', rect(79, 443, 133, 504)),
        ('Café G', 'space', 'Café G', rect(188, 443, 241, 522)),
        ('1-wing-hall', 'corridor', 'Hall',
         [[133, 443], [188, 443], [188, 522], [210, 522], [210, 574], [125, 574], [125, 527], [133, 527]]),
        ('1-walkway', 'corridor', 'Walkway to the Palace', rect(210, 537, 315, 558)),
    ],
    '2': [
        ('Calderwood Hall', 'space', 'Calderwood Hall', rect(149, 229, 242, 307)),
        ('Hostetter Gallery', 'space', 'Hostetter Gallery · Special exhibitions', rect(149, 356, 242, 416)),
        ('2-wing-hall', 'corridor', 'Hall',
         [[134, 229], [149, 229], [149, 307], [210, 307], [210, 356], [149, 356], [149, 416], [134, 416]]),
    ],
}

# Short names written on the map (the full name shows when a room is picked)
SHORT = {'Spanish Chapel': 'Sp. Chapel', 'Macknight Room': 'Macknight', 'Blue Room': 'Blue', 'Yellow Room': 'Yellow',
         'Second Floor Stairhall': 'Stairhall', 'Early Italian Room': 'Early Italian', 'Raphael Room': 'Raphael',
         'Dutch Room': 'Dutch', 'Second Floor Passage': 'Passage', 'Tapestry Room': 'Tapestry',
         'Third Floor Stairhall': 'Stairhall', 'Veronese Room': 'Veronese', 'Titian Room': 'Titian',
         'Gothic Room': 'Gothic', 'Third Floor Passage': 'Passage'}
LABEL_AT = {'Cloisters': (160, 546), 'Rear Hall': (107, 490)}

# Doors: (room a, room b, point), in the same page coordinates as the rooms of that building.
PALACE_DOORS = {
    '1': [('Courtyard', 'Cloisters', (177, 537)), ('Rear Hall', 'Cloisters', (108, 535)),
          ('Rear Hall', 'Cloisters', (234, 438)), ('1-restrooms', 'Rear Hall', (95, 495)),
          ('Cloisters', 'Spanish Cloister', (177, 556)), ('Cloisters', 'Spanish Cloister', (245, 556)),
          ('Spanish Cloister', 'Chinese Loggia', (177, 585)), ('Spanish Cloister', 'Spanish Chapel', (244, 585)),
          ('Cloisters', 'Macknight Room', (254, 461)), ('Cloisters', 'Blue Room', (254, 492)),
          ('Macknight Room', 'Vatichino', (285, 472)), ('Vatichino', 'Blue Room', (286, 486)),
          ('Blue Room', 'Fenway Gallery', (263, 556)), ('Fenway Gallery', 'Yellow Room', (263, 579)),
          ('Spanish Cloister', 'Fenway Gallery', (254, 573))],
    '2': [('Second Floor Stairhall', 'Early Italian Room', (233, 236)),
          ('Early Italian Room', 'Raphael Room', (263, 260)), ('Raphael Room', 'Short Gallery', (267, 323)),
          ('Short Gallery', 'Little Salon', (267, 347)), ('Short Gallery', 'Tapestry Room', (233, 335)),
          ('Little Salon', 'Tapestry Room', (233, 380)), ('Tapestry Room', 'Second Floor Passage', (98, 323)),
          ('Second Floor Passage', 'Dutch Room', (103, 303)), ('Dutch Room', 'Second Floor Stairhall', (119, 236))],
    '3': [('Third Floor Stairhall', 'Veronese Room', (234, 77)), ('Veronese Room', 'Titian Room', (268, 104)),
          ('Titian Room', 'Long Gallery', (268, 163)), ('Long Gallery', 'Chapel', (120, 174)),
          ('Gothic Room', 'Third Floor Stairhall', (120, 77)), ('Gothic Room', 'Third Floor Passage', (107, 143)),
          ('Third Floor Passage', 'Chapel', (100, 163)), ('Third Floor Passage', 'Long Gallery', (120, 160))],
}
WING_DOORS = {
    '1': [('Tickets', '1-entrance-hall', (129, 672)), ('Store', '1-entrance-hall', (125, 610)),
          ('Living Room', '1-entrance-hall', (200, 600)), ('1-entrance-hall', '1-wing-hall', (165, 574)),
          ('Studio', '1-wing-hall', (133, 500)), ('Café G', '1-wing-hall', (188, 449)),
          ('1-wing-hall', '1-walkway', (210, 547)), ('1-walkway', 'Cloisters', (315, 547))],
    '2': [('2-wing-hall', 'Calderwood Hall', (149, 290)), ('2-wing-hall', 'Hostetter Gallery', (149, 386))],
}

# Icons: (type, x, y). Palace ones in page 5 points, New Wing ones in the shared frame.
PALACE_AMENITIES = {
    '1': [('restroom', 66, 470), ('restroom', 66, 498), ('elevator', 114, 528), ('stairs', 170, 437)],
    '2': [('elevator', 113, 317), ('stairs', 170, 226)],
    '3': [('elevator', 113, 156), ('stairs', 170, 69)],
}
WING_AMENITIES = {
    '1': [('entrance', 170, 691), ('info', 88, 672), ('coat', 176, 600), ('dining', 214, 470),
          ('shop', 102, 610), ('elevator', 118, 547), ('stairs', 181, 533), ('stairs', 181, 560)],
    '2': [('elevator', 120, 331), ('stairs', 175, 322), ('stairs', 175, 344),
          ('restroom', 127, 300), ('restroom-all', 127, 361)],
}
PALACE_LABELS = {
    '1': [('Monk’s Garden', 'place', 150, 622), ('Worthington Street Lobby', 'note', 150, 418)],
    '2': [], '3': [],
}
WING_LABELS = {
    '1': [('Entrance · Evans Way', 'note', 170, 705), ('Jordan Garden', 'place', 300, 590),
          ('Restrooms & lockers one floor down', 'note', 181, 582)],
    '2': [('No way to the Palace from this floor', 'note', 260, 330)],
}

FLOORS = [
    ('1', 'Floor 1', 'Entrance · Café G · Store · Courtyard · Spanish Cloister · Yellow and Blue Rooms', 1),
    ('2', 'Floor 2', 'Dutch Room · Raphael Room · Tapestry Room · Calderwood Hall · Hostetter Gallery', 2),
    ('3', 'Floor 3', 'Titian Room · Veronese Room · Gothic Room · Long Gallery · Chapel', 3),
]

# Object number -> room (see the module notes)
ROOM_CODES = {
    '1': 'Yellow Room', '3': 'Blue Room', '6': 'Spanish Chapel', '7': 'Spanish Cloister', '11': 'Macknight Room',
    '14': 'Chinese Loggia', '33': 'Vatichino',
    '15': 'Early Italian Room', '16': 'Raphael Room', '17': 'Short Gallery', '18': 'Little Salon',
    '19': 'Tapestry Room', '20': 'Second Floor Passage', '21': 'Dutch Room',
    '25': 'Veronese Room', '26': 'Titian Room', '27': 'Long Gallery', '28': 'Chapel',
    '29': 'Third Floor Passage', '30': 'Gothic Room',
}
WALLS = {'n': 'north wall', 's': 'south wall', 'e': 'east wall', 'w': 'west wall', 'c': 'in a case'}
STOLEN = {'P21w27', 'P21s9', 'P21w24', 'P3s5'}   # taken in the 1990 theft; the empty frames still hang
PLACE_NOTE = 'Isabella placed every work herself, and it stays where she put it.'
STOLEN_NOTE = 'Stolen in 1990 and never found. Its empty frame still hangs here.'


def shift(points, dx, dy):
    return [[round(x + dx, 1), round(y + dy, 1)] for x, y in points]


def build_floors():
    floors = []
    for fid, label, area, order in FLOORS:
        dx, dy = PALACE_SHIFT[0], PALACE_SHIFT[1] + LEVEL_SHIFT[fid]
        wy = WING2_SHIFT if fid == '2' else 0
        rooms, doors, amen, labels = [], [], [], []
        for rid, kind, name, poly in PALACE[fid]:
            r = {'id': rid, 'kind': kind, 'name': name, 'poly': shift(poly, dx, dy)}
            if kind == 'gallery': r['label'] = SHORT.get(rid, rid)
            if rid in LABEL_AT: r['labelAt'] = shift([LABEL_AT[rid]], dx, dy)[0]
            rooms.append(r)
        for rid, kind, name, poly in WING.get(fid, []):
            rooms.append({'id': rid, 'kind': kind, 'name': name, 'poly': shift(poly, 0, wy)})
        for a, b, (x, y) in PALACE_DOORS[fid]:
            doors.append({'a': a, 'b': b, 'at': [x + dx, y + dy], 'width': 6.0, 'axis': 'o'})
        for a, b, (x, y) in WING_DOORS.get(fid, []):
            doors.append({'a': a, 'b': b, 'at': [x, y + wy], 'width': 6.0, 'axis': 'o'})
        for t, x, y in PALACE_AMENITIES[fid]:
            amen.append({'type': t, 'at': [x + dx, y + dy]})
        for t, x, y in WING_AMENITIES.get(fid, []):
            amen.append({'type': t, 'at': [x, y + wy]})
        for text, kind, x, y in PALACE_LABELS[fid]:
            labels.append({'text': text, 'kind': kind, 'at': [x + dx, y + dy]})
        for text, kind, x, y in WING_LABELS.get(fid, []):
            labels.append({'text': text, 'kind': kind, 'at': [x, y + wy]})
        ids = {r['id'] for r in rooms}
        for d in doors:
            assert d['a'] in ids and d['b'] in ids, (fid, d)
        floors.append({'id': fid, 'label': label, 'area': area, 'order': order, 'transform': [1, 0, 0],
                       'rooms': rooms, 'closed': [], 'amenities': amen, 'labels': labels, 'doors': doors})
    return {'about': 'Built by tools/build_gardner_map.py from the Isabella Stewart Gardner Museum visitor map.',
            'source': SOURCE, 'units': 'pdf-points', 'defaultFloor': '1', 'galleryWord': 'Room', 'floors': floors}


def build_works(floors):
    where = {r['id']: f['id'] for f in floors['floors'] for r in f['rooms']}
    guide = json.load(open(ROOT / 'data' / 'guides' / f'{MUSEUM}.json'))
    out, unplaced = [], 0
    for w in guide['works']:
        acc = w.get('accession') or ''
        m = re.match(r'[A-Z]+(\d+)([nsewc])?', acc)
        room = ROOM_CODES.get(m[1]) if m else None
        if not room:
            unplaced += 1
            continue
        a = {'id': f'isgm-{w["id"]}', 'title': w['title'], 'artist': w.get('artist', ''),
             'date': str(w['year']) if w.get('year') is not None else '', 'year': w.get('year'),
             'accession': acc, 'type': (w.get('type') or '').capitalize(),
             'gallery': room, 'galleryName': ' · '.join(filter(None, [room, WALLS.get(m[2] or '')])),
             'floor': where[room], 'placeNote': STOLEN_NOTE if acc in STOLEN else PLACE_NOTE,
             'url': w.get('url') or f'https://www.wikidata.org/wiki/{w["id"]}', 'wikidata': w['id']}
        if acc in STOLEN: a['stolen'] = True
        if w.get('image'):
            a['image'] = 'https://commons.wikimedia.org/wiki/Special:FilePath/' + urllib.parse.quote(w['image']) + '?width=600'
            a['imageCredit'] = 'Wikimedia Commons'
        out.append({k: v for k, v in a.items() if v not in (None, '')})
    out.sort(key=lambda a: (a['floor'], a['gallery'], -(len(a.get('image', '')) > 0), a.get('year') or 0))
    doc = {'source': 'Wikidata (CC0), pictures from Wikimedia Commons; rooms from the museum’s object numbers',
           'checked': time.strftime('%Y-%m-%d'), 'count': len(out), 'complete': False, 'artworks': out}
    return doc, unplaced


def main():
    OUT.mkdir(exist_ok=True)
    floors = build_floors()
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    works, unplaced = build_works(floors)
    (OUT / 'artworks.json').write_text(json.dumps(works, ensure_ascii=False, separators=(',', ':')))
    by = {}
    for a in works['artworks']: by[a['gallery']] = by.get(a['gallery'], 0) + 1
    print(f'{works["count"]} works placed ({sum(1 for a in works["artworks"] if "image" in a)} with pictures), '
          f'{unplaced} without a known room')
    for k in sorted(by): print(f'  {k}: {by[k]}')


if __name__ == '__main__':
    main()
