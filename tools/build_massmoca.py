#!/usr/bin/env python3
"""Build the MASS MoCA map guide (run: python3 tools/build_massmoca.py).

    data/massmoca/floors.json    Basement, Floor 1, Floor 2 and Floor 3 of the campus, seen from above (flat 2D)
    data/massmoca/artworks.json  works on view, each in the building and floor where it is shown
    data/massmoca/images/        the works' pictures, made smaller for phones

The map: MASS MoCA's visitor map, October 2026 edition ("MASSMoCA_MuseumMap_Digital_September2026", the PDF
behind the map link on massmoca.org/visit: indd.adobe.com/view/publication/7c66baf8-2fb5-4a53-898b-548c9e1293ec/
2sht/publication-web-resources/pdf/MuseumMap_Digital_English.pdf). It is a vector PDF: the yellow (galleries),
lilac (non-gallery spaces) and grey (closed buildings) shapes below are its own outlines, in PDF points of
page 2 (Floor 1 and the Basement inset) and page 3 (Floor 2 on the left, Floor 3 on the right). Seasonal
galleries (hatched on the map), the outdoor paths and the courtyards are drawn by hand over the map.
The pages draw each floor in a different place; SHIFT moves Floors 2 and 3 and the Basement onto Floor 1, so
the elevators and stairs of a building sit on top of each other, which is how directions link floors.
The map is drawn as the museum draws it, with north to the right.

The works: massmoca.org is behind a Cloudflare check, so its pages were read once by hand in November 2026
and written into tools/data/massmoca_works.tsv (descriptions are short summaries in our own words). The Sol
LeWitt Wall Drawing Retrospective (Building 7) has a page for each of its wall drawings; the retrospective runs
in order, so the floor is guessed from the year (early works on Floor 1, late works on Floor 3). The other
works are placed where the museum's October 2026 map lists them. Pictures come from massmoca.org's uploads
folder (which answers plain requests), read one every half second and kept in .cache/massmoca.
"""
import io
import json
import subprocess
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'massmoca'
CACHE = ROOT / '.cache' / 'massmoca'
DATA = ROOT / 'tools' / 'data' / 'massmoca_works.tsv'
SOURCE = 'MASS MoCA visitor map, October 2026 edition'

# where each floor's drawing sits in the PDF, moved onto Floor 1's footing
SHIFT = {'B': (241.5, -1), '1': (0, 0), '2': (211, -1), '3': (7.5, -1)}
K = 2   # PDF points x2, so names fit inside the rooms like on the other museums' maps


def rect(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


# (id, kind, name, poly in the floor's own PDF points, short label for galleries)
ROOMS = {
    'B': [
        ('Building 10 · Basement', 'gallery', 'Building 10 basement · coatroom, lockers, restrooms · Allovers',
         [[61, 461], [88, 461], [88, 494], [19, 494], [30, 462], [53, 461]], 'Allovers'),
    ],
    '1': [
        ("Joe's Field", 'corridor', "Path across Joe's Field (outdoors)",
         [[212, 277], [232, 277], [232, 466], [212, 466], [212, 450], [185, 450], [185, 430], [212, 430]], None),
        ('The Pipes', 'gallery', 'Taryn Simon: The Pipes (outdoors)', rect(180, 330, 214, 385), 'The Pipes'),
        ('Franz West totems', 'gallery', "Franz West: Les Pommes d'Adam (outdoors)", rect(127, 425, 185, 452), 'Franz West'),
        ('The Speed Way', 'corridor', 'The Speed Way · bridge over the Hoosic River', rect(222, 464, 266, 488), None),
        ('Building 14 · Boiler House', 'gallery', 'Building 14 · Boiler House (seasonal, May to October)',
         [[169, 487], [221, 475], [231, 501], [180, 515]], 'Boiler House'),
        ('Building 15 · Kiefer', 'gallery', 'Building 15 · Hall Art Foundation · Anselm Kiefer (seasonal, May to October)',
         [[86, 520], [169, 487], [180, 515], [102, 554]], 'Kiefer'),
        ('Path to C.A.V.U.', 'corridor', 'Path to the C.A.V.U. Skyspace', rect(212, 265, 313, 277), None),
        ('C.A.V.U. Skyspace', 'gallery', 'James Turrell: C.A.V.U. (Skyspace)', rect(232, 238, 258, 265), 'C.A.V.U.'),
        ('Building 6 · Turrell', 'gallery', 'Building 6 · James Turrell galleries (Perfectly Clear, Hind Sight)',
         [[309, 90], [341, 90], [342, 159], [292, 159], [292, 111]], 'Turrell'),
        ('Building 6 · Lounge', 'gallery', 'Building 6 · Lounge · James Turrell',
         [[292, 159], [354, 159], [354, 178], [372, 178], [372, 200], [342, 201], [327, 200], [313, 249], [313, 265],
          [292, 265]], 'Lounge'),
        ('Bike tunnel', 'gallery', 'Bike tunnel under Building 6 · Mary Lum (seasonal, May to October)',
         rect(372, 177, 396, 200), 'Mary Lum'),
        ('Courtyard D', 'corridor', 'Courtyard D · entrance to Building 6',
         [[327, 200], [372, 200], [372, 291], [313, 291], [313, 249]], None),
        ('Building 8 · The Chalet', 'space', 'Building 8 · The Chalet (seasonal)', rect(292, 278, 315, 378), None),
        ('Building 7 · Floor 1', 'gallery', 'Building 7 · Sol LeWitt: Early Career',
         [[343, 291], [372, 291], [372, 379], [325, 379], [325, 340], [343, 340]], 'LeWitt'),
        ('Courtyard C', 'corridor', 'Courtyard C · walkway to Building 7',
         [[315, 379], [372, 379], [372, 405], [335, 405], [335, 461], [315, 461]], None),
        ('Dré Pavilion', 'space', 'Dré Pavilion', rect(335, 410, 365, 451), None),
        ('Building 4 · Floor 1', 'gallery', 'Building 4 · Spatial Poems · Michael E. Smith',
         [[374, 401], [420, 401], [416, 517], [386, 517], [386, 490], [374, 490]], 'Building 4'),
        ('R&D Store', 'space', 'The Research & Development Store · 50 Years of PUNK',
         [[374, 490], [386, 490], [386, 517], [416, 517], [416, 531], [374, 531]], None),
        ('Building 10 · Lobby', 'corridor', 'Building 10 · Lobby · tickets, gift shop, Lickety Split café',
         [[272, 461], [374, 460], [374, 493], [262, 493]], None),
        ('Hunter hallway', 'gallery', 'Building 11 · Hunter hallway · Carly Glovinski',
         [[292, 493], [305, 494], [305, 571], [292, 571]], 'Almanac'),
        ('Hunter Center', 'space', 'Building 11 · The Hunter Center for the Performing Arts', rect(257, 493, 292, 571), None),
        ('Courtyard A', 'corridor', 'Courtyard A · main entrance plaza',
         [[305, 493], [374, 493], [374, 600], [327, 600], [327, 534], [305, 534]], None),
    ],
    '2': [
        ('The Prow', 'gallery', 'Building 6 · The Prow', [[145, 29], [156, 29], [167.4, 95], [94, 95]], 'The Prow'),
        ('Building 6 · Floor 2', 'gallery', 'Building 6 · second floor · Louise Bourgeois, James Turrell and more',
         [[94, 95], [167.4, 95], [186, 202], [81, 202], [81, 112]], 'Building 6'),
        ('Event Space', 'space', 'Building 6 · Event Space', [[81, 202], [109, 202], [96, 242], [91, 266], [81, 266]], None),
        ('Ramp to Building 8', 'corridor', 'Ramp between Building 6 and Building 8',
         [[109, 202], [119, 202], [102, 251], [101, 266], [91, 266], [96, 242]], None),
        ('Building 8 · Floor 2', 'gallery', 'Building 8 · Spencer Finch: Cosmic Latte',
         [[81, 266], [103, 266], [103, 381], [100, 461], [86, 461], [89, 380], [81, 369]], 'Cosmic Latte'),
        ('Building 7 · Floor 2', 'gallery', 'Building 7 · Sol LeWitt: Mid-Career',
         [[132, 293], [171, 293], [171, 381], [103, 381], [103, 342], [132, 342]], 'LeWitt'),
        ('Building 5', 'gallery', 'Building 5 · Laurent Grasso: Metaphysical Maze',
         [[161, 202], [186, 202], [194, 233], [194, 341], [211, 341], [211, 403], [161, 403]], 'Building 5'),
        ('Building 4 · Floor 2', 'gallery', 'Building 4 · Jimena Sarno: Rhapsody',
         [[162, 403], [211, 403], [210, 435], [188, 435], [188, 520], [205, 521], [204, 544], [162, 544]], 'Building 4'),
        ('Building 10 · Floor 2', 'corridor', 'Building 10 · second floor', [[59, 461], [100, 461], [100, 493], [52, 494]], None),
        ('Kidspace', 'gallery', 'Building 10 · Kidspace (always free)', rect(100, 461, 145, 493), 'Kidspace'),
        ('Hunter Mezzanine', 'gallery', 'Building 11 · Hunter Mezzanine · Performing Arts Posters',
         rect(61, 494, 93, 571), 'Mezzanine'),
        ('Swing Space', 'space', 'Building 11 · Swing Space · Rehearsal Hall', rect(93, 534, 116, 571), None),
    ],
    '3': [
        ('Building 6 · Floor 3', 'gallery', 'Building 6 · third floor · Laurie Anderson, Gunnar Schonbeck and more',
         [[323, 202], [390, 202], [366, 63], [323, 63], [285, 112], [285, 202]], 'Building 6'),
        ('Building 5 · Floor 3', 'gallery', 'Building 5 · upper level', [[365, 202], [390, 202], [399, 233], [399, 249], [365, 249]],
         'B5'),
        ('Building 7 · Floor 3', 'gallery', 'Building 7 · Sol LeWitt: Late Career',
         [[336, 293], [365, 293], [365, 381], [307, 381], [307, 342], [336, 342]], 'LeWitt'),
        ('Building 4 · Floor 3', 'gallery', 'Building 4 · Daniela Rivera: Hacia Cuando (To When)',
         [[365, 403], [415, 403], [411, 439], [367, 439]], 'Rivera'),
        ('Club B10', 'space', 'Building 10 · Club B10', [[267, 461], [287, 461], [287, 494], [254, 494]], None),
        ('Building 10 · Floor 3', 'corridor', 'Building 10 · third floor', [[287, 461], [367, 461], [367, 493], [287, 494]], None),
    ],
}

# grey buildings on the map: part of the campus, not open to visitors
CLOSED = {
    'B': [[[88, 461], [115, 461], [115, 494], [88, 494]], [[14, 494], [62, 494], [62, 503], [14, 503]]],
    '1': [[[372, 200], [397, 200], [406, 231], [406, 339], [421, 339], [421, 401], [372, 401]],
          [[269, 283], [253, 284], [254, 296], [244, 297], [247, 352], [246, 358], [229, 355], [224, 379], [241, 383],
           [235, 412], [259, 417], [271, 354]],
          rect(374, 531, 416, 612), rect(305, 534, 327, 571), [[203, 331], [200, 303], [220, 300], [223, 328]],
          [[166, 571], [166, 558], [232, 523], [249, 523], [249, 571]]],
    '2': [rect(142, 461, 163, 493), [[188, 520], [188, 435], [210, 435], [206, 521]], rect(162, 531, 205, 612),
          [[46, 571], [46, 494], [61, 494], [61, 571]]],
    '3': [[[399, 238], [399, 341], [416, 341], [416, 402], [365, 402], [365, 249], [399, 249]],
          [[307, 266], [285, 266], [285, 368], [295, 380], [292, 465], [304, 465], [307, 381]],
          rect(367, 439, 409, 544), rect(251, 494, 321, 571), rect(367, 531, 409, 612)],
}

DOORS = {   # (room, room, where) in the floor's own PDF points
    'B': [],
    '1': [("Joe's Field", 'The Pipes', (212, 357)), ("Joe's Field", 'Franz West totems', (185, 440)),
          ("Joe's Field", 'The Speed Way', (226, 465)), ("Joe's Field", 'Path to C.A.V.U.', (222, 277)),
          ('Path to C.A.V.U.', 'C.A.V.U. Skyspace', (245, 265)), ('Path to C.A.V.U.', 'Courtyard D', (313, 270)),
          ('The Speed Way', 'Building 14 · Boiler House', (226, 484)), ('Building 14 · Boiler House', 'Building 15 · Kiefer', (175, 500)),
          ('The Speed Way', 'Building 10 · Lobby', (266, 476)), ('Courtyard D', 'Building 6 · Lounge', (348, 200)),
          ('Building 6 · Lounge', 'Building 6 · Turrell', (320, 159)), ('Building 6 · Lounge', 'Bike tunnel', (372, 189)),
          ('Courtyard D', 'Building 7 · Floor 1', (358, 291)), ('Courtyard D', 'Building 8 · The Chalet', (303, 284)),
          ('Courtyard C', 'Building 7 · Floor 1', (340, 379)), ('Courtyard C', 'Building 8 · The Chalet', (315, 375)),
          ('Courtyard C', 'Dré Pavilion', (335, 430)), ('Courtyard C', 'Building 10 · Lobby', (325, 461)),
          ('Building 10 · Lobby', 'Building 4 · Floor 1', (374, 475)), ('Building 4 · Floor 1', 'R&D Store', (380, 490)),
          ('Building 10 · Lobby', 'Hunter hallway', (298, 493)), ('Building 10 · Lobby', 'Hunter Center', (275, 493)),
          ('Building 10 · Lobby', 'Courtyard A', (332, 493)), ('Courtyard A', 'R&D Store', (374, 525))],
    '2': [('The Prow', 'Building 6 · Floor 2', (130, 95)), ('Building 6 · Floor 2', 'Event Space', (95, 202)),
          ('Building 6 · Floor 2', 'Ramp to Building 8', (114, 202)), ('Ramp to Building 8', 'Building 8 · Floor 2', (96, 266)),
          ('Building 6 · Floor 2', 'Building 5', (175, 202)), ('Building 8 · Floor 2', 'Building 7 · Floor 2', (103, 365)),
          ('Building 7 · Floor 2', 'Building 5', (166, 340)), ('Building 5', 'Building 4 · Floor 2', (185, 403)),
          ('Building 8 · Floor 2', 'Building 10 · Floor 2', (93, 461)), ('Building 10 · Floor 2', 'Kidspace', (100, 477)),
          ('Building 10 · Floor 2', 'Hunter Mezzanine', (77, 494)), ('Hunter Mezzanine', 'Swing Space', (93, 550))],
    '3': [('Building 6 · Floor 3', 'Building 5 · Floor 3', (377, 202)), ('Club B10', 'Building 10 · Floor 3', (287, 477))],
}

# Stairs and elevators, in Floor 1's footing (one point per shaft, so the floors link), with the floors they serve.
# Read from the map's icons: they sit within a few points of each other from floor to floor.
VERTICAL = [
    ('elevator', 339, 195, '123'), ('elevator', 366, 355, '123'), ('elevator', 405, 407, '123'), ('elevator', 318, 474, 'B123'),
    ('stairs', 346, 168, '123'), ('stairs', 345, 130, '23'), ('stairs', 389, 204, '23'), ('stairs', 368, 328, '123'),
    ('stairs', 395, 457, '12'), ('stairs', 381, 432, '23'), ('stairs', 292, 475, 'B123'),
]
AMENITIES = {   # in the floor's own PDF points, from the map's icons
    'B': [('water', 33, 469), ('coat', 81, 467), ('restroom', 33, 483)],
    '1': [('restroom-all', 299, 231), ('info', 348, 466), ('shop', 325, 468), ('shop', 380, 523), ('dining', 274, 485),
          ('info', 366, 486), ('entrance', 332, 495), ('entrance', 348, 203)],
    '2': [('water', 122, 93), ('restroom-all', 123, 115), ('restroom-all', 87, 259), ('restroom-all', 154, 372),
          ('restroom-all', 118, 468), ('water', 138, 469)],
    '3': [('water', 326, 93), ('restroom-all', 322, 115), ('restroom-all', 358, 372), ('restroom-all', 323, 468),
          ('nursing', 335, 468), ('water', 323, 483)],
}
LABELS = {
    'B': [('Basement of Building 10: take the stairs or elevator from the lobby', 'note', 55, 515)],
    '1': [('Main Entrance · Welcome', 'note', 340, 505), ('Entrance to Building 6', 'note', 350, 212),
          ("Joe's Field", 'place', 230, 300), ('Hoosic River', 'place', 255, 420), ('Main parking lot', 'place', 250, 600)],
    '2': [('All buildings connect on the second floor', 'note', 150, 20)],
    '3': [('Floor 3: reach each building by its own stairs or elevator', 'note', 330, 40)],
}
FLOORS = [
    ('B', 'Basement', 'Building 10 basement · coatroom, lockers, restrooms · Allovers', -1),
    ('1', 'Floor 1', 'Lobby · tickets · café · gift shop · James Turrell · Sol LeWitt early works · Building 4 · '
                     'Hunter Center · outdoor art', 0),
    ('2', 'Floor 2', 'All buildings connect · Building 6 (Louise Bourgeois, James Turrell) · Building 5 · Sol LeWitt '
                     'mid-career · Spencer Finch · Jimena Sarno · Kidspace', 1),
    ('3', 'Floor 3', 'Building 6 (Laurie Anderson, Gunnar Schonbeck) · Sol LeWitt late works · Daniela Rivera', 2),
]


def pt(fid, x, y):
    dx, dy = SHIFT[fid]
    return [round((x + dx) * K, 1), round((y + dy) * K, 1)]


def base_pt(x, y):          # a point already in Floor 1's footing
    return [round(x * K, 1), round(y * K, 1)]


def build_floors():
    floors = []
    for fid, label, area, order in FLOORS:
        rooms = []
        for rid, kind, name, poly, short in ROOMS[fid]:
            r = {'id': rid, 'kind': kind, 'name': name, 'poly': [pt(fid, x, y) for x, y in poly]}
            if kind == 'gallery': r['label'] = short or rid
            rooms.append(r)
        ids = {r['id'] for r in rooms}
        doors = [{'a': a, 'b': b, 'at': pt(fid, x, y), 'width': 6 * K, 'axis': 'o'} for a, b, (x, y) in DOORS[fid]]
        for d in doors:
            assert d['a'] in ids and d['b'] in ids, (fid, d)
        amen = [{'type': t, 'at': pt(fid, x, y)} for t, x, y in AMENITIES[fid]]
        amen += [{'type': t, 'at': base_pt(x, y)} for t, x, y, fl in VERTICAL if fid in fl]
        labels = [{'text': t, 'kind': k, 'at': pt(fid, x, y)} for t, k, x, y in LABELS[fid]]
        closed = [{'poly': [pt(fid, x, y) for x, y in p]} for p in CLOSED[fid]]
        floors.append({'id': fid, 'label': label, 'area': area, 'order': order, 'transform': [1, 0, 0],
                       'rooms': rooms, 'closed': closed, 'amenities': amen, 'labels': labels, 'doors': doors})
    return {'about': 'Built by tools/build_massmoca.py from the MASS MoCA visitor map (October 2026 edition). '
                     'Building outlines are the map’s own; seasonal galleries, paths and courtyards are drawn over it, '
                     'so they are approximate. The map shows north to the right, as the museum’s map does.',
            'source': SOURCE, 'units': 'half points', 'defaultFloor': '1', 'galleryWord': 'Building', 'floors': floors}


# ---- works ------------------------------------------------------------------------------------------------------

PLACE = {   # place codes in the works file -> room id
    'B6-1': 'Building 6 · Turrell', 'B6-1,B6-2': 'Building 6 · Turrell', 'B6-2': 'Building 6 · Floor 2',
    'B6-3': 'Building 6 · Floor 3', 'CAVU': 'C.A.V.U. Skyspace', 'B15': 'Building 15 · Kiefer',
    'B14': 'Building 14 · Boiler House', 'B8-2': 'Building 8 · Floor 2', 'B4-1': 'Building 4 · Floor 1',
    'B4-2': 'Building 4 · Floor 2', 'B4-3': 'Building 4 · Floor 3', 'R&D Store': 'R&D Store',
    'B11-1': 'Hunter hallway', 'B10-B': 'Building 10 · Basement', 'B10-1': 'Building 10 · Lobby', 'B5': 'Building 5',
    'Courtyard A': 'Courtyard A', 'Mary Lum': 'Bike tunnel', 'walkway': 'Courtyard C',
}
OUTDOOR = {'pipes': 'The Pipes', 'west': 'Franz West totems', 'puryear': 'Courtyard A', 'kubisch': 'Courtyard A',
           'gummer': 'Courtyard A'}
NOTES = {
    'map': 'Listed here on the museum’s October 2026 map.',
    'lewitt': ('In the Sol LeWitt Wall Drawing Retrospective (Building 7, on view until 2043). The retrospective runs '
               'in order of date, so the floor is worked out from the year.'),
    'site': 'Placed from the museum’s page for this work.',
}
SITE_PLACED = {'puryear': 'At the southern edge of the campus, toward Main Street.',
               'kubisch': 'In the 80-foot clock tower; you hear the bells outdoors.',
               'gummer': 'Outdoors near the entry walkway and the clock tower.',
               'swartz': 'In the covered walkway between the lobby and the Sol LeWitt building.',
               'lexier': 'The coins are hidden all over the museum; the lobby is a good place to start.',
               'manning': 'The texts are beside mill windows all over the museum.',
               'lum': 'In the bike tunnel under Building 6.'}


def lewitt_room(year):
    if year <= 1981: return 'Building 7 · Floor 1'
    if year <= 1994: return 'Building 7 · Floor 2'
    return 'Building 7 · Floor 3'


def year_of(date):
    import re
    m = re.search(r'(\d{4})', date or '')
    return int(m[1]) if m else None


def picture(key, url):
    """Download once (politely) and save a phone-sized JPEG; returns the app path."""
    if not url: return None
    CACHE.mkdir(parents=True, exist_ok=True)
    raw = CACHE / (key + Path(url).suffix.lower())
    if not raw.exists():
        out = subprocess.run(['curl', '-s', '-f', '-m', '60', '-A', 'Mozilla/5.0 (gallery-guide)', url],
                             capture_output=True, check=False).stdout
        time.sleep(0.5)
        if not out: return None
        raw.write_bytes(out)
    dest = OUT / 'images' / f'{key}.jpg'
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        im = Image.open(io.BytesIO(raw.read_bytes()))
        im = im.convert('RGBA') if im.mode in ('P', 'LA') else im
        if im.mode == 'RGBA':
            bg = Image.new('RGB', im.size, 'white'); bg.paste(im, mask=im.split()[3]); im = bg
        im = im.convert('RGB')
        im.thumbnail((1000, 1000))
        im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)
    return f'data/massmoca/images/{key}.jpg'


def build_works(floors):
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    out = []
    for line in DATA.read_text().splitlines():
        if not line.strip() or line.startswith('#'): continue
        kind, key, artist, title, date, place, medium, desc, credit, img, url = line.split('\t')
        year = year_of(date)
        if kind == 'lewitt':
            room, note = lewitt_room(year), NOTES['lewitt']
        else:
            room = OUTDOOR.get(key) or PLACE[place]
            note = SITE_PLACED.get(key) or (NOTES['map'] if place not in ('outdoor', 'walkway') else NOTES['site'])
        floor, gname = rooms[room]
        a = {'id': f'mm-{key}', 'title': title, 'artist': artist, 'date': date, 'year': year, 'medium': medium,
             'creditLine': credit, 'gallery': room, 'galleryName': gname, 'floor': floor, 'placeNote': note,
             'description': desc, 'url': url}
        a['descriptionKind'] = ('Summary of the artist’s instructions, from MASS MoCA’s page for this wall drawing'
                                if kind == 'lewitt' else 'Summary from MASS MoCA’s page for this work')
        if kind == 'lewitt': a['type'] = 'Wall drawing'
        p = picture(f'mm-{key}', img)
        if p:
            a['image'], a['imageCredit'], a['imageSource'] = p, 'MASS MoCA', img
        out.append({k: v for k, v in a.items() if v not in (None, '')})
    order = {r['id']: i for f in floors['floors'] for i, r in enumerate(f['rooms'])}
    forder = {f['id']: f['order'] for f in floors['floors']}
    out.sort(key=lambda a: (forder[a['floor']], order[a['gallery']], a.get('year') or 0))
    assert len({a['id'] for a in out}) == len(out)
    return {'source': 'MASS MoCA website (massmoca.org exhibition and wall drawing pages) and the museum’s October 2026 '
                      'map; pictures from massmoca.org',
            'checked': '2026-11-04', 'count': len(out), 'complete': True, 'artworks': out}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    floors = build_floors()
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    works = build_works(floors)
    (OUT / 'artworks.json').write_text(json.dumps(works, ensure_ascii=False, separators=(',', ':')))
    by = {}
    for a in works['artworks']: by[a['gallery']] = by.get(a['gallery'], 0) + 1
    print(f'{works["count"]} works, {sum("image" in a for a in works["artworks"])} with pictures')
    for k, n in by.items(): print(f'  {k}: {n}')


if __name__ == '__main__':
    main()
