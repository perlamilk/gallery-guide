#!/usr/bin/env python3
"""Build the Bruce Museum (Greenwich, CT) map guide (run: python3 tools/build_bruce.py).

    data/bruce/floors.json       the Ground Floor (lobby) and the Gallery Level, seen from above (flat 2D)
    data/bruce/artworks.json     what is on view, placed in its gallery
    data/bruce/images/           pictures, made smaller for phones
    data/guides/Q4978055.json    the same list for the museum page, plus collection works not known to be on view

Where the information comes from
--------------------------------
The walls are the architects' own floor plans of the 2023 building: "BruceFloorPlans_Web_1.png" on EskewDumezRipple's
project page (eskewdumezripple.com/the-bruce-museum.html), three plans side by side (01 Ground Level, 02 Mezzanine /
Basement Level, 03 Gallery Level), north up, with a 0-50 ft scale bar. Coordinates are pixels of that image at
3600 px wide, in the frame of the Ground Level plan; the Gallery Level plan sits 2395 px to the right of it on the
sheet, so its points are measured there and moved back by that much (the outside landscape lines up). The scale bar
gives 167 px for 50 ft (0.091 m a pixel).

The plans carry no room names. What each room is comes from the architects' text (lobby, café, shop and lecture hall on
the park level, 25 ft below the galleries; a U-shaped gallery wing around an open-air light court; the old house's
north door kept as the school-group entrance), from Architectural Record (the sculpture gallery on the south links the
art and science wings), from the reopening press (the mineral gallery lies between the sculpture gallery and the
changing science gallery; a 4,500 sq ft gallery for changing art shows; five galleries for the permanent collection)
and from the furniture drawn on the plans (the shop's display tables, the restroom stalls, the café counter and its
terrace tables, the lecture hall's stage). Names of the rooms in the old building and which show is in which gallery
were approximate until Nov 11 2026, when the museum's own floor plans in its Bloomberg Connects guide (read in the app
on Grazi's Mac) gave every room its name: the north rooms of the old house are the Cohen Education Wing (classrooms),
the centre is the Changing Science Gallery and the west the Permanent Science Galleries. The Mezzanine is staff space
and collection storage: not drawn.

Works: brucemuseum.org asks AI agents not to read it (robots.txt disallows Claude-User and Claude-Web), and its
Bloomberg Connects guide refuses outside readers, so nothing here comes from the museum's own pages. Current shows come
from press releases and news (Resnicow, Greenwich Free Press, CT Examiner, ctvisit.com) and search listings; pictures
and collection works from Wikidata and Wikimedia Commons (free licences).
"""
import io
import json
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'bruce'
CACHE = ROOT / '.cache' / 'bruce'
MUSEUM = 'Q4978055'
NAME = 'Bruce Museum'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
PLANS = 'https://tff-edr.imgix.net/assets/images/thumbnails/assets/uploads/446/BruceFloorPlans_Web_1.png?w=3600&q=90'
SITE = 'https://brucemuseum.org/'
K = 2                     # map units are plan pixels x 2 (text and icons are sized in map units)
S = 0.4                   # transform: map units -> app units; drawn about 3x life size so labels fit the rooms
WALK = 0.13               # walking: 0.0456 m a unit / 0.35 m a router point
COMMONS = 'Wikimedia Commons'


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# ---- Ground Floor (park level: free to enter during museum hours) -------------------------------------------------
GROUND = [
    # id, kind, name shown, polygon, short label
    ('Lobby', 'space', 'Cunniffe Grand Hall · Admissions',
     [(722, 585), (876, 585), (876, 740), (722, 740)], None),
    ('Museum Store', 'space', 'Museum Store', rect(722, 412, 806, 582), None),
    ('Restrooms G', 'space', 'Restrooms', rect(806, 412, 876, 582), None),
    ('Café', 'space', 'Dining Room (café)', [(752, 740), (876, 740), (876, 878), (752, 878)],
     None),
    ('Lecture Hall Corridor', 'corridor', 'Corridor', rect(720, 740, 752, 898), None),
    ('Lecture Hall', 'space', 'Goergen Auditorium', rect(572, 742, 718, 898), None),
]
GROUND_CLOSED = [rect(540, 775, 570, 895), rect(808, 744, 872, 772)]          # stage store; staff stair
GROUND_DOORS = [('Lobby', 'Museum Store', (764, 584)), ('Lobby', 'Restrooms G', (840, 584)), ('Lobby', 'Café', (814, 740)),
                ('Lobby', 'Lecture Hall Corridor', (736, 740)), ('Lecture Hall Corridor', 'Lecture Hall', (719, 830)),
                ('Lecture Hall Corridor', 'Café', (752, 790))]
GROUND_AMEN = [('entrance', 874, 664), ('info', 769, 626), ('shop', 764, 500), ('restroom', 841, 500),
               ('elevator', 702, 567), ('stairs', 815, 618), ('dining', 845, 850),
               ('coat', 735, 600)]
GROUND_LABELS = [('MAIN ENTRANCE ←', 925, 664), ('Café terrace', 830, 925), ('Bruce Park', 960, 820),
                 ('Light court (open air) ↖', 650, 715)]
GROUND_NOTES = [('Stairs up to the galleries', 739, 655), ('Front desk', 775, 640)]

# ---- Gallery Level (the old house and the new wing, all on one level) ---------------------------------------------
GALLERY = [
    ('Changing Exhibitions', 'gallery', 'Changing Art Gallery (about 4,500 sq ft, William L. Richter Art Wing)',
     rect(726, 160, 868, 503), 'Changing Exhibitions'),
    ('Gallery Hall', 'corridor', 'Susan & Bill Mahoney Gallery Lobby and the Vicki Netter Fitzgerald Gallery (the long hall)',
     [(682, 160), (718, 160), (718, 512), (868, 512), (868, 580), (636, 580), (636, 515), (682, 515)], None),
    ('Main Stair', 'corridor', 'Top of the main stairs from the lobby', rect(822, 584, 868, 740), None),
    ('Art Gallery East', 'gallery', 'Grossman Family Gallery', rect(722, 584, 818, 740), 'Grossman'),
    ('Art Gallery South-East', 'gallery', 'Edward & Barbara Netter Foundation Gallery', rect(724, 744, 868, 900), 'Netter'),
    ('Art Gallery South', 'gallery', 'Art gallery between the Blavatnik and Netter galleries (Richter Art Wing)',
     rect(626, 744, 716, 900), 'South'),
    ('Art Gallery South-West', 'gallery', 'The Blavatnik Family Gallery', rect(540, 744, 616, 900), 'Blavatnik'),
    ('Sculpture Gallery', 'gallery', 'Sculpture Gallery: the link between the art and science wings, with views of '
     'Greenwich Harbor and Long Island Sound', rect(404, 776, 520, 900), 'Sculpture'),
    ('South Passage', 'corridor', 'Passage from the science galleries to the Sculpture Gallery', rect(408, 735, 520, 776),
     None),
    ('Mineral Gallery', 'gallery', 'Robert R. Wiener Mineral Gallery (about 200 minerals)', rect(410, 664, 546, 735),
     'Minerals'),
    ('Changing Science', 'gallery', 'Changing Science Gallery',
     [(452, 446), (490, 446), (490, 512), (636, 512), (636, 585), (590, 585), (590, 662), (410, 662), (410, 575),
      (448, 575), (448, 512)], 'Changing Science'),
    ('Science Hall', 'gallery', 'Permanent Science Galleries: Natural Cycles Shape Our Land', rect(232, 622, 392, 800),
     'Permanent Science'),
    ('West Galleries', 'gallery', 'Permanent Science Galleries (north part)',
     [(262, 505), (448, 505), (448, 575), (410, 575), (410, 622), (232, 622), (232, 560), (262, 560)], 'Science'),
    ('North Galleries', 'space', 'Cohen Education Wing: Woodburn, Selander and Trustees 2021 classrooms',
     [(270, 352), (367, 352), (367, 418), (360, 418), (360, 446), (448, 446), (448, 505), (262, 505), (262, 446),
      (270, 446)], None),
    ('Rotunda', 'corridor', 'Education Entrance hall and Quiet Room (Cohen Education Wing)',
     [(436, 352), (500, 352), (500, 418), (680, 418), (680, 446), (360, 446), (360, 418), (436, 418)], None),
    ('Restrooms U1', 'space', 'Restrooms', rect(560, 354, 680, 416), None),
    ('Restrooms U2', 'space', 'Restrooms', rect(548, 448, 660, 510), None),
]
GALLERY_CLOSED = [rect(572, 160, 682, 330),                                                      # staff, freight lift
                  [(592, 584), (714, 584), (714, 740), (548, 740), (548, 662), (592, 662)]]     # open-air light court
GALLERY_DOORS = [('Gallery Hall', 'Changing Exhibitions', (722, 243)), ('Gallery Hall', 'Changing Exhibitions', (722, 428)),
                 ('Gallery Hall', 'Changing Exhibitions', (770, 508)), ('Gallery Hall', 'Main Stair', (845, 582)),
                 ('Gallery Hall', 'Art Gallery East', (770, 582)), ('Art Gallery East', 'Art Gallery South-East', (770, 742)),
                 ('Art Gallery South-East', 'Art Gallery South', (720, 821)),
                 ('Art Gallery South', 'Art Gallery South-West', (621, 821)),
                 ('Art Gallery South-West', 'Sculpture Gallery', (530, 821)),
                 ('Sculpture Gallery', 'South Passage', (466, 776)), ('South Passage', 'Mineral Gallery', (478, 735)),
                 ('Mineral Gallery', 'Changing Science', (478, 663)), ('South Passage', 'Science Hall', (400, 755)),
                 ('Science Hall', 'West Galleries', (300, 622)), ('West Galleries', 'Changing Science', (448, 540)),
                 ('West Galleries', 'North Galleries', (350, 505)), ('North Galleries', 'Rotunda', (364, 432)),
                 ('Changing Science', 'Rotunda', (471, 446)), ('Changing Science', 'Gallery Hall', (636, 548)),
                 ('Rotunda', 'Gallery Hall', (681, 432)), ('Rotunda', 'Restrooms U1', (620, 417)),
                 ('Changing Science', 'Restrooms U2', (592, 511))]
GALLERY_AMEN = [('stairs', 845, 630), ('elevator', 701, 564), ('elevator', 418, 600), ('restroom', 620, 385),
                ('restroom', 592, 480), ('entrance', 468, 356)]
GALLERY_LABELS = [('EDUCATION ENTRANCE ↑', 468, 330), ('Light court (open air)', 640, 680),
                  ('Windows to the harbor ↓', 560, 930)]
GALLERY_NOTES = [('Main stairs down to the lobby', 845, 700)]


def pt(x, y):
    return [round(x * K, 1), round(y * K, 1)]


def poly(q):
    return [pt(x, y) for x, y in q]


def inside(pt, pg):
    x, y = pt
    c = False
    for i in range(len(pg)):
        (x1, y1), (x2, y2) = pg[i], pg[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c


def floor(fid, label, order, area_text, spec, closed, doors, amen, labels, notes):
    rooms = []
    for rid, kind, name, pg, short in spec:
        r = {'id': rid, 'kind': kind, 'name': name, 'poly': poly(pg)}
        if short: r['label'] = short
        rooms.append(r)
    ids = [r['id'] for r in rooms]
    assert len(ids) == len(set(ids)), fid
    for a, b, at in doors:
        assert a in ids and b in ids, (fid, a, b)
    f = {'id': fid, 'label': label, 'order': order, 'transform': [S, 0, 0], 'walkScale': WALK, 'area': area_text, 'rooms': rooms,
         'closed': [{'poly': poly(c)} for c in closed],
         'amenities': [{'type': t, 'at': pt(x, y)} for t, x, y in amen],
         'labels': [{'text': t, 'kind': 'area', 'at': pt(x, y)} for t, x, y in labels],
         'notes': [{'text': t, 'kind': 'note', 'at': pt(x, y)} for t, x, y in notes],
         'doors': [{'a': a, 'b': b, 'at': pt(*at), 'width': 16, 'axis': 'o'} for a, b, at in doors]}
    for a in f['amenities']:
        if not any(inside(a['at'], r['poly']) for r in rooms):
            print(f'  note: {label} {a["type"]} at {a["at"]} is outside the rooms (routes use the nearest room)')
    return f


def build_floors():
    floors = [
        floor('G', 'Ground Floor', 0, 'Lobby, café, Museum Store, lecture hall, classrooms: free to enter during museum '
              'hours', GROUND, GROUND_CLOSED, GROUND_DOORS, GROUND_AMEN, GROUND_LABELS, GROUND_NOTES),
        floor('U', 'Gallery Level', 1, 'Art and science galleries: the Richter Art Wing, the Sculpture Gallery, the '
              'Mineral Gallery and the science galleries of the old house', GALLERY, GALLERY_CLOSED, GALLERY_DOORS,
              GALLERY_AMEN, GALLERY_LABELS, GALLERY_NOTES),
    ]
    return {'about': 'Built by tools/build_bruce.py. Walls traced from the architects’ (EskewDumezRipple) floor plans of '
                     'the 2023 building; room names from the museum’s own floor plans in its Bloomberg Connects guide '
                     '(Nov 2026). Which show is in which gallery is still a guess. The Mezzanine (staff) is not drawn.',
            'source': 'EskewDumezRipple floor plans (2023) and the Bruce’s floor plans in Bloomberg Connects (Nov 2026)',
            'units': 'pixels of the architects’ plan sheet at 3600 px wide, x 2 (0.046 m a unit), north up',
            'defaultFloor': 'G', 'galleryWord': 'Gallery', 'floors': floors}


# ---- pictures ------------------------------------------------------------------------------------------------------

def commons_url(name, width=1000):
    return 'https://commons.wikimedia.org/wiki/Special:FilePath/' + urllib.parse.quote(name) + f'?width={width}'


def picture(key, src):
    """src: a Commons file name. Wikimedia often answers 429 to cloud machines: wait and try again, politely."""
    if not src: return None
    dest = OUT / 'images' / f'{key}.jpg'
    rel = f'data/bruce/images/{key}.jpg'
    if dest.exists(): return rel
    raw = CACHE / 'img' / (key + '.bin')
    if not raw.exists():
        raw.parent.mkdir(parents=True, exist_ok=True)
        for wait in (0, 20, 60, 120):
            time.sleep(wait or 2)
            r = subprocess.run(['curl', '-s', '-L', '-m', '90', '-A', UA, '-w', '%{http_code}', '-o', str(raw),
                                commons_url(src)], capture_output=True, text=True)
            if r.stdout.strip() == '200' and raw.stat().st_size > 5000: break
            raw.unlink(missing_ok=True)
        else:
            print(f'  no picture (Commons busy): {src}')
            return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    im = Image.open(io.BytesIO(raw.read_bytes())).convert('RGB')
    im.thumbnail((1000, 1000))
    im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)
    return rel


# ---- what is on view ------------------------------------------------------------------------------------------------
# (key, gallery, title, artist, date, medium, text, Commons picture, source url, credit line, temporary)
AS = ('American Stories from Sargent to O’Keeffe: A Partnership with The Newark Museum of Art (Oct 15, 2026 – Oct 10, '
      '2027). ')
AS_URL = 'https://www.resnicow.com/press/release/2026-07-american-stories-brings-masterworks-of-american-art-to-the-bruce/'
ON_VIEW = [
    ('american-stories', 'Changing Exhibitions', 'American Stories from Sargent to O’Keeffe', 'Exhibition',
     'Oct 15, 2026 – Oct 10, 2027', None,
     'More than 40 masterworks of American art lent by The Newark Museum of Art, in four sections (Identity, Belonging, '
     'Belief and Making), each opened by a question for visitors: paintings by John Singer Sargent, Albert Bierstadt, '
     'Edward Hopper and Georgia O’Keeffe, sculpture by Alexander Calder, Louise Nevelson and Martin Puryear, and '
     'Mickalene Thomas. Curated by Margarita Karasoulas. Included with admission.',
     None, AS_URL, None, True),
    ('sargent-thursby', 'Changing Exhibitions', 'Mrs. Charles Thursby (Alice Brisbane)', 'John Singer Sargent',
     'about 1897–1898', 'Oil on canvas, 78 ¼ × 39 ½ in.',
     AS + 'Lent by The Newark Museum of Art.', 'Mrs. Charles Thursby.jpg', AS_URL, None, True),
    ('hopper-sheridan', 'Changing Exhibitions', 'The Sheridan Theatre', 'Edward Hopper', '1937', 'Oil on canvas',
     AS + 'Lent by The Newark Museum of Art.', None, AS_URL, None, True),
    ('okeeffe-white-flower', 'Changing Exhibitions', 'White Flower on Red Earth, No. 1', 'Georgia O’Keeffe', '1943',
     'Oil on canvas', AS + 'Lent by The Newark Museum of Art.', None, AS_URL, None, True),
    ('thomas-tracey-norman', 'Changing Exhibitions', 'Isn’t She Lovely, Tracey Norman', 'Mickalene Thomas', '2022',
     'Rhinestones, acrylic and oil paint on canvas mounted on wood panel, 72 × 96 in.',
     AS + 'Lent by The Newark Museum of Art.', None, AS_URL, None, True),
    ('yellin', 'Art Gallery East', 'Dustin Yellin: Politics of Eternity', 'Dustin Yellin', 'July 25, 2026 – March 14, 2027',
     'Glass, collage', 'An exhibition organized by the American Federation of Arts around Politics of Eternity (2020), an '
     'installation of glass about eleven feet long and nearly 11,000 pounds, with thousands of cut-out images sealed '
     'between its layers; excerpts of Yellin’s short film Goodnight, Lamby play nearby. Organized at the Bruce by '
     'Jordan Hillman, Assistant Curator of Art.', None,
     'https://greenwichfreepress.com/around-town/arts/major-exhibition-of-artist-dustin-yellin-exploring-visions-of-'
     'humanity-and-nature-opens-at-the-bruce-museum-this-july-250602/', None, True),
    ('devasher', 'Art Gallery South-East', 'Rohini Devasher: Solar Poetics', 'Rohini Devasher',
     'Aug 22 – Nov 29, 2026', 'Four-channel video; works on copper',
     'The artist’s first solo museum show in the United States, built around One Hundred Thousand Suns (2023), a '
     'four-channel video new to the Bruce’s collection, drawn from the Kodaikanal Solar Observatory in India and its '
     'archive of about 157,000 portraits of the sun; with her works on copper. Closes November 29, 2026.', None,
     'https://greenwichfreepress.com/around-town/arts/the-bruce-museum-presents-rohini-devashers-first-us-institutional-'
     'exhibition-251837/', None, True),
    ('sandman', 'Art Gallery South', 'Jo Sandman: What Remains', 'Jo Sandman', 'Aug 29, 2026 – Jan 17, 2027', None,
     'A show of work by the American artist Jo Sandman.', None, 'https://brucemuseum.org/exhibitions/', None, True),
    ('fair', 'Changing Science', 'A Great Breach in Nature: Aerial Photography by J Henry Fair', 'J Henry Fair',
     'Sept 29, 2026 – Feb 7, 2027', 'Photographs',
     'Aerial photographs of industrial damage to the land and water, from Fair’s series Industrial Scars: art that '
     'explains science.', None, 'https://brucemuseum.org/exhibitions/', None, True),
    ('minerals', 'Mineral Gallery', 'Robert R. Wiener Mineral Gallery', 'Permanent science gallery', None, None,
     'About 200 minerals, most of them given by Robert R. Wiener: large crystals from around the world, a meteorite you '
     'can touch and minerals that glow under black light.', 'Bruce Museum 04 - Minerals Gallery.JPG',
     'https://en.wikipedia.org/wiki/Bruce_Museum', 'photo of the mineral cases before the 2023 rebuilding', False),
    ('natural-cycles', 'Science Hall', 'Natural Cycles Shape Our Land', 'Permanent science exhibition', None, None,
     'The Bruce’s permanent science exhibition: geology, fossils, archaeology and the Native peoples of the area, how '
     'Greenwich’s land and shore changed from before the settlers to the 1900s, a woodland diorama with local wildlife '
     'and birds, and a marine tank with small fish, crabs and sea stars.', 'Bruce Museum 01 - birds.JPG',
     'https://en.wikipedia.org/wiki/Bruce_Museum', 'photo of the bird cases before the 2023 rebuilding', False),
    ('sculpture-gallery', 'Sculpture Gallery', 'The Sculpture Gallery', 'Gallery', None, None,
     'The light-filled gallery that joins the William L. Richter Art Wing to the science wing, with views of Greenwich '
     'Harbor and Long Island Sound. The Bruce’s sculpture runs from Auguste Rodin, Hiram Powers and Frederick '
     'MacMonnies to George Segal.', 'Bruce Museum Gallery Tim Hursley.jpg',
     'https://www.architecturalrecord.com/articles/16363-the-bruce-museum-by-eskewdumezripple-integrates-spaces-for-'
     'science-and-art', 'Timothy Hursley', False),
    ('lobby', 'Lobby', 'The new Bruce: lobby and main stairs', 'Building', '2023', None,
     'EskewDumezRipple’s 2023 wing put the lobby, café, store and lecture hall at the level of Bruce Park, 25 feet '
     'below the galleries; the stairs climb past the rock outcrop the building is set into. The whole ground floor is '
     'free during museum hours.', 'Bruce Museum Stairway Photo Tim Hursley.jpg',
     'https://eskewdumezripple.com/the-bruce-museum.html', 'Timothy Hursley', False),
]
WHERE = {
    'Changing Exhibitions': 'Which gallery the show is in is a guess: the largest gallery for changing art shows.',
    'Art Gallery East': 'Which gallery the show is in is a guess.',
    'Art Gallery South-East': 'Which gallery the show is in is a guess.',
    'Art Gallery South': 'Which gallery the show is in is a guess.',
    'Changing Science': 'The Changing Science Gallery, as the museum’s own floor plan names it.',
    'Mineral Gallery': 'Between the Sculpture Gallery and the changing science gallery, as the museum describes it; '
                       'its exact rooms are approximate.',
    'Science Hall': 'The Permanent Science Galleries, as the museum’s own floor plan names them.',
}

# collection works from Wikidata and Commons: not known to be on view (the Bruce has no online collection)
# (key, title, artist, date, Commons picture, Wikidata id or source)
COLLECTION = [
    ('ochtman-mianus', 'On the Mianus River', 'Leonard Ochtman', None, 'Ochtman On the Mianus river.jpg', 'Q117006006'),
    ('bellows-lundberg', 'August Lundberg (No. 2)', 'George Bellows', '1907',
     'George Bellows - Portrait of August Lundberg No.2 (1907).jpg', 'Q132143703'),
    ('bouguereau-faun', 'Faun and Bacchante', 'William-Adolphe Bouguereau', None, 'FauneBacchante W-A Bouguereau.JPG',
     'Q58845104'),
    ('edwards-ronda', 'The Bridge at Ronda, Pyrenees', 'George Wharton Edwards', None,
     'The Bridge at Ronda, Pyrenees by George Wharton Edwards.jpg', 'Q141591571'),
    ('edwards-monhegan', 'Farmhouses on Monhegan Island', 'George Wharton Edwards', None,
     'Farmhouses on Monhegan Island by George Wharton Edwards.jpg', 'Q141592393'),
    ('bricher-coastal', 'Coastal Scene', 'Alfred Thomson Bricher', None,
     'Coastal Scene by Alfred Thomson Bricher, Bruce Museum.jpg', 'commons'),
    ('dumond-margaree', 'Margaree Forks', 'Frank Vincent DuMond', None,
     'Margaree Forks by Frank Vincent DuMond, oil on canvas, Bruce Museum.jpg', 'commons'),
    ('verhas-flower-pot', 'The Broken Flower Pot', 'Jan Verhas', None, 'Jan Verhas - The broken flower pot.jpg', 'commons'),
]


def build_works(floors):
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    works = []
    for key, room, title, artist, date, medium, text, pic, url, credit, temp in ON_VIEW:
        fl, gname = rooms[room]
        img = picture(f'bruce-{key}', pic) if pic else None
        a = {'id': f'bruce-{key}', 'title': title, 'artist': artist, 'date': date, 'medium': medium,
             'description': text, 'gallery': room, 'galleryName': gname, 'floor': fl,
             'placeNote': WHERE.get(room, 'Where the architects’ plans and the museum’s descriptions put it.'),
             'url': url, 'image': img,
             'imageCredit': (f'{credit}, via {COMMONS}' if credit else COMMONS) if img else None}
        if temp: a['temporary'] = True
        works.append({k: v for k, v in a.items() if v not in (None, '', [])})
    return {'source': 'Bruce Museum: current shows from press releases and news; pictures from Wikimedia Commons',
            'checked': time.strftime('%Y-%m-%d'), 'count': len(works), 'complete': False, 'artworks': works}


def build_guide(works):
    rows = []
    for a in works['artworks']:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a['artist'], 'date': a.get('date'),
                     'medium': a.get('medium'), 'url': a['url'], 'imageUrl': a.get('image'), 'onView': True,
                     'gallery': a['gallery'], 'floor': a['floor']}.items() if v not in (None, '')})
    for key, title, artist, date, pic, src in COLLECTION:
        url = (f'https://www.wikidata.org/wiki/{src}' if src.startswith('Q')
               else 'https://commons.wikimedia.org/wiki/File:' + urllib.parse.quote(pic.replace(' ', '_')))
        rows.append({k: v for k, v in {'id': f'bruce-{key}', 'title': title, 'artist': artist, 'date': date,
                     'year': int(date[:4]) if date else None, 'url': url,
                     'imageUrl': picture(f'bruce-{key}', pic), 'onView': False}.items() if v not in (None, '')})
    return {'museum': MUSEUM, 'name': NAME, 'checked': time.strftime('%Y-%m-%d'),
            'source': 'Bruce Museum: news and press releases on its shows; Wikidata and Wikimedia Commons',
            'onViewKnown': True,
            'note': 'The Bruce has no online collection, and its website asks AI tools not to read it, so this list is '
                    'built from news of its current shows and from free pictures on Wikimedia Commons. The shows are '
                    'on view now; which gallery each is in is a guess. The paintings at the end belong to the Bruce '
                    'but may not be on view.',
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
