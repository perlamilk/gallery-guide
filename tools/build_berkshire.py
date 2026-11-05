#!/usr/bin/env python3
"""Build the Berkshire Museum (Pittsfield, MA) map guide (run: python3 tools/harvest_berkshire.py, then this).

    data/berkshire/floors.json    the First Floor and the Second Floor, seen from above (flat 2D)
    data/berkshire/artworks.json  what is on view, placed in its gallery
    data/berkshire/images/        pictures, made smaller for phones
    data/guides/Q4892280.json     the same list for the museum page, plus collection works not known to be on view

Where the information comes from
--------------------------------
First Floor: the architects' own plan of the 2026 renovation, "Berkshire Museum Plan" by StudioHAU, in their press kit
on v2com-newswire (dossier 2757-65, "StudioHAU Completes Extensive Renovation and Redesign of the Berkshire Museum's
First Floor Galleries, Aquarium and Public Spaces", Feb 2026). Only the 800 px preview is public; coordinates are pixels
of that preview (the scale bar gives about 56 px for 20 ft). The plan numbers its rooms (1 Entry, 2 Lobby, 3 Museum
Shop, 4 Cafe, 5 Events Hall, 6 Hall of History, 7 Cabinet of Curiosities, 8 Aquarium, 9 Gallery of Paleontology,
10 Gallery of Ecology, 11 Diorama Room, 12 Immersed in Nature, 13 Children's Activity Area, 14 Boardroom, 15 Offices,
16 Dock), so the First Floor rooms are EXACT; restrooms, stairs and the elevator follow what is drawn. The plan has
South Street (the main entrance) at the top; it is not turned north up.

Second Floor: no plan is published. StudioHAU's interior isometric shows galleries in a ring around the middle of the
building; the 2021 reopening press (Rural Intelligence, Macaroni KID, The Berkshire Edge) names the Ellen Crane
Memorial Room, "Objects and Their Stories" (about 5,000 sq ft, with Pahat the mummy and the Winged Victory cast), a
quiet sitting room at the top of the stairs looking over South Street, two restrooms and two learning spaces; the
museum's listing puts "Soulful Creatures" in Galleries 206-208. Where each room is on that floor is APPROXIMATE, and the
floor says so.

Works: berkshiremuseum.org's robots.txt disallows ClaudeBot, Claude-Web and anthropic-ai, so nothing here comes from
the museum's own pages. What is on view comes from the reopening press (iBerkshires, The Berkshire Eagle, StudioHAU's
press text, NEWS10, The Berkshire Edge); collection works from the museum's Google Arts & Culture pages
(tools/harvest_berkshire.py); free pictures from Wikimedia Commons.
"""
import io
import json
import re
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'berkshire'
CACHE = ROOT / '.cache' / 'berkshire'
MUSEUM = 'Q4892280'
NAME = 'Berkshire Museum'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
PLAN = ('https://www.v2com-newswire.com/fr/salle-de-presse/categories/architecture-institutionnelle/dossiers-de-presse/'
        '2757-65/studiohau-paracheve-la-renovation-majeure-et-le-reamenagement-complet-du-rez-de-chaussee-du-berkshire-museum')
K = 4                     # map units are plan pixels x 4 (text and icons are sized in map units)
S = 0.4                   # transform: map units -> app units
WALK = 0.078              # walking: 0.0272 m a unit / 0.35 m a router point
COMMONS = 'Wikimedia Commons'


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# ---- First Floor (the 2026 StudioHAU plan, rooms numbered on the plan) ---------------------------------------------
FIRST = [
    # id, kind, name shown, polygon, short label
    ('Entry', 'space', 'Entry (doors from South Street)', rect(395, 212, 452, 268), None),
    ('Lobby', 'space', 'Lobby: tickets, coats and lockers',
     [(453, 215), (520, 215), (520, 242), (552, 242), (552, 328), (453, 328)], None),
    ('Front Hall', 'corridor', 'Front hall', rect(307, 268, 452, 290), None),
    ('Museum Shop', 'space', 'Museum Shop', rect(323, 212, 393, 268), None),
    ('Cafe', 'space', 'Café (small)', rect(291, 205, 322, 268), None),
    ('Children', 'space', 'Children’s Activity Area', rect(235, 268, 307, 316), None),
    ('Restrooms 1', 'space', 'Restrooms', rect(322, 290, 395, 343), None),
    ('Main Stairs', 'corridor', 'Main stairs', rect(397, 290, 450, 342), None),
    ('Events Hall', 'space', 'Events Hall (lectures and films)', rect(553, 208, 613, 327), None),
    ('Hall of History', 'gallery', 'Hall of History (Gallery 1)', rect(523, 328, 613, 394), 'History'),
    ('Aquarium', 'gallery', 'Feigenbaum Aquarium',
     [(322, 345), (500, 345), (500, 362), (522, 362), (522, 470), (330, 470), (322, 452)], 'Aquarium'),
    ('Cabinets of Curiosities', 'gallery', 'Cabinets of Curiosities (Gallery 2)', rect(525, 396, 613, 562),
     'Curiosities'),
    ('Paleontology', 'gallery', 'Paleontology & Geology (Gallery 3), with the glowing rock room',
     rect(449, 477, 523, 562), 'Fossils'),
    ('Ecology', 'gallery', 'Gallery of Ecology', rect(399, 477, 447, 562), 'Ecology'),
    ('World in Miniature', 'gallery', 'The World in Miniature: the Jonas Studios dioramas (Gallery 5)',
     rect(323, 477, 397, 562), 'Miniature'),
    ('Immersed in Nature', 'gallery', 'Immersed in Nature (Galleries 6 and 7), with the 360° room',
     rect(235, 316, 320, 528), 'Nature'),
]
FIRST_CLOSED = [rect(232, 205, 290, 268),                  # boardroom
                rect(522, 203, 552, 240),                  # stair and service core
                rect(180, 395, 232, 625),                  # loading dock
                [(232, 528), (320, 528), (320, 565), (553, 565), (553, 588), (480, 588), (480, 625), (232, 625)]]  # offices
FIRST_DOORS = [('Entry', 'Lobby', (453, 240)), ('Entry', 'Front Hall', (423, 268)), ('Front Hall', 'Lobby', (452, 279)),
               ('Front Hall', 'Museum Shop', (357, 268)), ('Front Hall', 'Cafe', (315, 268)),
               ('Front Hall', 'Children', (307, 279)), ('Front Hall', 'Restrooms 1', (358, 290)),
               ('Front Hall', 'Main Stairs', (423, 290)), ('Lobby', 'Events Hall', (552, 290)),
               ('Lobby', 'Hall of History', (537, 328)), ('Hall of History', 'Aquarium', (522, 380)),
               ('Hall of History', 'Cabinets of Curiosities', (570, 395)),
               ('Cabinets of Curiosities', 'Paleontology', (524, 520)), ('Paleontology', 'Ecology', (448, 520)),
               ('Ecology', 'World in Miniature', (398, 520)), ('World in Miniature', 'Immersed in Nature', (321, 515)),
               ('Immersed in Nature', 'Aquarium', (321, 403)), ('Children', 'Immersed in Nature', (270, 316))]
FIRST_AMEN = [('entrance', 423, 214), ('info', 488, 292), ('coat', 470, 250), ('shop', 358, 240), ('dining', 306, 236),
              ('restroom', 358, 316), ('stairs', 423, 316), ('stairs', 430, 545), ('elevator', 437, 490)]
FIRST_LABELS = [('SOUTH STREET · MAIN ENTRANCE ↑', 423, 180), ('Offices (staff)', 380, 600)]
FIRST_NOTES = [('Main stairs up to the Second Floor', 423, 355), ('Front desk', 488, 308),
               ('Walk-through tunnels into the aquarium', 420, 410)]

# ---- Second Floor (approximate: no plan is published) ---------------------------------------------------------------
SECOND = [
    ('Upper Hall', 'corridor', 'Second floor hall, at the top of the main stairs',
     [(233, 268), (452, 268), (452, 290), (450, 290), (450, 342), (397, 342), (397, 290), (320, 290), (320, 316),
      (233, 316)], None),
    ('Sitting Room', 'space', 'Quiet sitting room with the big window over South Street', rect(395, 212, 452, 268),
     None),
    ('Learning Spaces', 'space', 'Learning spaces: art studio and science lab (programs)', rect(233, 212, 393, 268),
     None),
    ('Restrooms 2', 'space', 'Restrooms', rect(322, 290, 395, 343), None),
    ('Crane Room', 'gallery', 'Ellen Crane Memorial Room', rect(453, 212, 613, 290), 'Crane Room'),
    ('Objects and Their Stories', 'gallery', 'Objects and Their Stories (collection galleries)', rect(523, 290, 613, 528),
     'Objects'),
    ('Galleries 206-208', 'gallery', 'Galleries 206–208: changing exhibitions',
     [(233, 316), (320, 316), (320, 470), (523, 470), (523, 528), (233, 528)], '206–208'),
]
SECOND_CLOSED = [rect(322, 345, 522, 470)]                 # middle of the building (not public)
SECOND_DOORS = [('Upper Hall', 'Sitting Room', (423, 268)), ('Upper Hall', 'Learning Spaces', (300, 268)),
                ('Upper Hall', 'Crane Room', (452, 279)), ('Upper Hall', 'Restrooms 2', (358, 290)),
                ('Upper Hall', 'Galleries 206-208', (276, 316)), ('Crane Room', 'Objects and Their Stories', (568, 290)),
                ('Objects and Their Stories', 'Galleries 206-208', (523, 500))]
SECOND_AMEN = [('stairs', 423, 316), ('stairs', 430, 515), ('elevator', 437, 490), ('restroom', 358, 316)]
SECOND_LABELS = [('South Street ↑', 423, 180), ('Middle of the building (not public)', 422, 408)]
SECOND_NOTES = []
LABEL_AT = {'Galleries 206-208': (276, 430)}


def pt(x, y):
    return [round(x * K, 1), round(y * K, 1)]


def poly(q):
    return [pt(x, y) for x, y in q]


def inside(p, pg):
    x, y = p
    c = False
    for i in range(len(pg)):
        (x1, y1), (x2, y2) = pg[i], pg[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c


def floor(fid, label, order, area_text, spec, closed, doors, amen, labels, notes, approx=False):
    rooms = []
    for rid, kind, name, pg, short in spec:
        r = {'id': rid, 'kind': kind, 'name': name, 'poly': poly(pg)}
        if short: r['label'] = short
        if rid in LABEL_AT: r['labelAt'] = pt(*LABEL_AT[rid])
        rooms.append(r)
    ids = [r['id'] for r in rooms]
    assert len(ids) == len(set(ids)), fid
    for a, b, at in doors:
        assert a in ids and b in ids, (fid, a, b)
    f = {'id': fid, 'label': label, 'order': order, 'transform': [S, 0, 0], 'walkScale': WALK, 'area': area_text,
         'rooms': rooms, 'closed': [{'poly': poly(c)} for c in closed],
         'amenities': [{'type': t, 'at': pt(x, y)} for t, x, y in amen],
         'labels': [{'text': t, 'kind': 'area', 'at': pt(x, y)} for t, x, y in labels],
         'notes': [{'text': t, 'kind': 'note', 'at': pt(x, y)} for t, x, y in notes],
         'doors': [{'a': a, 'b': b, 'at': pt(*at), 'width': 16, 'axis': 'o'} for a, b, at in doors]}
    if approx: f['approximate'] = True
    for a in f['amenities']:
        if not any(inside(a['at'], r['poly']) for r in rooms):
            print(f'  note: {label} {a["type"]} at {a["at"]} is outside the rooms (routes use the nearest room)')
    return f


def build_floors():
    floors = [
        floor('1', 'First Floor', 0, 'Entry, lobby, shop, café, restrooms, the aquarium and the permanent galleries '
              '(from the architects’ plan)', FIRST, FIRST_CLOSED, FIRST_DOORS, FIRST_AMEN, FIRST_LABELS, FIRST_NOTES),
        floor('2', 'Second Floor', 1, 'Changing exhibitions, Objects and Their Stories, the Ellen Crane Memorial Room '
              '(room positions approximate)', SECOND, SECOND_CLOSED, SECOND_DOORS, SECOND_AMEN, SECOND_LABELS,
              SECOND_NOTES, approx=True),
    ]
    return {'about': 'Built by tools/build_berkshire.py. First Floor traced from the architects’ (StudioHAU) plan of the '
                     '2026 renovation, whose numbered rooms give every name. The Second Floor has no published plan: '
                     'its rooms come from news descriptions and are approximate. South Street (the main entrance) is '
                     'at the top.',
            'source': 'StudioHAU, Berkshire Museum Plan (press kit, v2com-newswire, 2026); news descriptions of the '
                      'second floor',
            'sourceUrl': PLAN,
            'units': 'pixels of the 800 px plan preview, x 4 (about 0.027 m a unit); South Street at the top',
            'approximate': True, 'defaultFloor': '1', 'galleryWord': 'Gallery', 'floors': floors}


# ---- pictures ------------------------------------------------------------------------------------------------------

def fetch(url, raw):
    """Wikimedia often answers 429 to cloud machines: wait and try again, politely."""
    for wait in (2, 30, 90, 180):
        time.sleep(wait)
        r = subprocess.run(['curl', '-s', '-L', '-m', '90', '-A', UA, '-w', '%{http_code}', '-o', str(raw), url],
                           capture_output=True, text=True)
        if r.stdout.strip() == '200' and raw.exists() and raw.stat().st_size > 3000: return True
        raw.unlink(missing_ok=True)
        if 'wikimedia' not in url: break
    return False


def picture(key, src):
    """src: ('commons', file name) or ('url', address)."""
    if not src: return None
    dest = OUT / 'images' / f'{key}.jpg'
    rel = f'data/berkshire/images/{key}.jpg'
    if dest.exists(): return rel
    if '--offline' in sys.argv: return None
    raw = CACHE / 'img' / (key + '.bin')
    if not raw.exists():
        raw.parent.mkdir(parents=True, exist_ok=True)
        kind, val = src
        url = ('https://commons.wikimedia.org/wiki/Special:FilePath/' + urllib.parse.quote(val) + '?width=960'
               if kind == 'commons' else val)
        if not fetch(url, raw):
            print(f'  no picture yet: {val}')
            return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        im = Image.open(io.BytesIO(raw.read_bytes())).convert('RGB')
    except Exception:
        raw.unlink()
        return None
    im.thumbnail((1000, 1000))
    im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)
    return rel


# ---- what is on view ------------------------------------------------------------------------------------------------
IB = 'https://www.iberkshires.com/story/83359/Berkshire-Museum-Unveils-Historic-Transformation-After-Yearlong-Renovation.html'
EAGLE = ('https://berkshireeagle.com/arts_and_culture/arts-theater/berkshire-museum-reopens-july-29/'
         'article_12a81674-7edf-443a-8e51-4adc94f7d5fb.html')
RI = 'https://www.ruralintelligence.com/berkshire-museum-opens-renovated-second-floor/'
SC_URL = 'https://www.news10.com/top-stories/ancient-animal-mummies-in-the-berkshires/'
SC = 'Soulful Creatures: Animal Mummies in Ancient Egypt (Oct 10, 2026 – Jan 17, 2027), lent by the Brooklyn Museum. '
AQ = 'Feigenbaum Aquarium. The photo shows the species, not the museum’s own animal. '
# (key, room, title, kind/artist, date, medium, text, picture, source url, picture credit, temporary)
ON_VIEW = [
    ('wally', 'Entry', 'Wally the Stegosaurus', 'Outdoor sculpture', None, None,
     'The giant stegosaurus on the museum’s front lawn on South Street, a Pittsfield favourite; you pass him on the way '
     'in.', None, 'https://berkshires.macaronikid.com/articles/60fd652d9c2b605f3766a762/'
     'second-floor-sneak-peek-at-the-berkshire-museum', None, False),
    ('lobby', 'Lobby', 'The new lobby', 'Building', '2026', None,
     'The light-filled lobby of the 2026 renovation by StudioHAU (Los Angeles), with Bradley Architects of Pittsfield: '
     'ticket desk with an accessible counter, seats, coat racks, lockers and wheelchairs to borrow. The building opened '
     'in 1903, founded by the paper-mill owner Zenas Crane as a “Museum of Natural History and Art”, words still carved '
     'over the door.', None, PLAN, None, False),
    ('hall-of-history', 'Hall of History', 'Hall of History', 'Permanent gallery', None, None,
     'The museum’s own story and Zenas Crane’s, with inventions and history from Pittsfield and the Berkshires: among '
     'them a painting of historic Wahconah Park, one of the oldest maps of Pittsfield, and art by Berkshire County '
     'students (the “Remembering Times Past” wall by Drury High School middle-schoolers).', None, IB, None, False),
    ('aquarium', 'Aquarium', 'Feigenbaum Aquarium', 'Live animals', None, None,
     'Moved up from the basement in 2026 and twice its old size, the aquarium is now the heart of the first floor: five '
     'floor-to-ceiling tanks set like a cave, a lit glass walkway that looks like flowing water, and walk-through '
     'tunnels from the Hall of History and from Immersed in Nature. Next to the tanks live land animals (snakes, geckos, '
     'dart frogs, tortoises, a blue-tongued skink, a chameleon), fed partly by a hydroponic garden.',
     None, PLAN, None, False),
    ('octopus', 'Aquarium', 'Caribbean reef octopus', 'Live animal', None, None,
     AQ + 'One of the new species since the 2026 reopening.', ('commons', 'CaribbeanReefOctopus.jpg'), EAGLE,
     None, False),
    ('jellyfish', 'Aquarium', 'Moon jellyfish', 'Live animal', None, None,
     AQ + 'New since the 2026 reopening.', ('commons', 'Aurelia aurita (Cnidaria) Luc Viatour.jpg'), EAGLE, None, False),
    ('bearded-dragon', 'Aquarium', 'Bearded dragon', 'Live animal', None, None,
     AQ + 'New since the 2026 reopening.', ('commons', 'Bartagame (fcm).jpg'), EAGLE, None, False),
    ('skink', 'Aquarium', 'Blue-tongued skink', 'Live animal', None, None,
     AQ + 'In the land-animal area beside the tanks.', ('commons', 'Tiliqua scincoides scincoides.jpg'), PLAN, None,
     False),
    ('chameleon', 'Aquarium', 'Chameleon', 'Live animal', None, None,
     AQ + 'In the land-animal area beside the tanks.', ('commons', 'Yemen Chameleon.jpg'), PLAN, None, False),
    ('cabinets', 'Cabinets of Curiosities', 'Cabinets of Curiosities', 'Permanent gallery', None, None,
     'Eight new red-oak cabinets inspired by Zenas Crane’s idea of a “window on the world”: weapons, jewellery, writing, '
     'paintings, musical instruments and natural history side by side, with drawers you can open and screens to '
     'explore. The objects change often, so curators can bring out more of the museum’s 40,000 things.', None, IB, None,
     False),
    ('paleontology', 'Paleontology', 'Paleontology & Geology', 'Permanent gallery', None, None,
     'Minerals, fossils, dinosaur bones and taxidermy in lit glass cases, with sculpture, paintings and scientific '
     'instruments among them, telling the story of the Earth before people.',
     ('commons', 'Berkshire Museum Fossilization Exhibit.jpg'), PLAN, 'photo of the fossil exhibit before the 2025–2026 '
     'renovation', False),
    ('glowing-rocks', 'Paleontology', 'The glowing rock room', 'Permanent exhibit', None, None,
     'A dark room in the middle of the Paleontology & Geology gallery, bigger than before, where minerals and objects '
     'made from them glow under special light. A favourite with children.', None, EAGLE, None, False),
    ('dioramas', 'World in Miniature', 'The World in Miniature: Jonas Studios dioramas', 'Dioramas', '1946–1970', None,
     'Fourteen miniature wildlife scenes the museum ordered from Jonas Studios between 1946 and 1970, each showing a '
     'habitat somewhere in the world and its animals. Jonas Studios restored them for the 2026 reopening; the room has '
     'a globe in the middle and a fibre-optic star map of the night sky over Pittsfield.', None, EAGLE, None, False),
    ('immersed', 'Immersed in Nature', 'Immersed in Nature', 'Permanent galleries', None, None,
     'Two galleries of the museum’s taxidermy in natural settings, with display cases, paintings and stones and fish '
     'native to Massachusetts. The selection changes from time to time.', ('commons', 'Berkshire Museum Bird Display.jpg'),
     PLAN, 'photo of a bird case before the 2025–2026 renovation', False),
    ('around-the-world', 'Immersed in Nature', 'Around the World 360', 'Immersive room', None, None,
     'A round walk-in projection room that takes you to ten scenes around the globe, with sound; the museum plans to '
     'add Berkshire places such as the top of Mount Greylock.', None, IB, None, False),
    ('soulful-creatures', 'Galleries 206-208', 'Soulful Creatures: Animal Mummies in Ancient Egypt', 'Exhibition',
     'Oct 10, 2026 – Jan 17, 2027', None,
     'A touring exhibition from the Brooklyn Museum’s Egyptian collection: mummified birds, cats, dogs and snakes with '
     'coffins, statues and amulets, and what they tell about how ancient Egyptians saw animals and the gods. In '
     'Galleries 206–208, through January 17, 2027.', None, SC_URL, None, True),
    ('ibis-coffin', 'Galleries 206-208', 'Ibis Coffin', 'Ancient Egypt, Ptolemaic Period', '305–30 B.C.E.',
     'Wood, silver, gold, rock crystal',
     SC + 'Brooklyn Museum 49.48a-b: a coffin for an ibis, the bird of the god Thoth, covered in silver and gold with '
     'rock-crystal eyes; it holds a simple ibis mummy. One of the touring show’s highlights.',
     ('commons', 'Ibis Coffin, 305-30 B.C.E., 49.48.jpg'), SC_URL, 'Brooklyn Museum', True),
    ('objects', 'Objects and Their Stories', 'Objects and Their Stories', 'Collection galleries', 'since 2021', None,
     'About 5,000 sq ft of the museum’s own art, science and history objects shown by theme, changing over time: '
     'Pittsfield Elm pictures and things carved from its wood, presidents’ portraits, musical instruments from around '
     'the world, animal skeletons.', None, RI, None, False),
    ('pahat', 'Objects and Their Stories', 'Pahat, the mummy', 'Ancient Egypt', None, None,
     'The museum’s Egyptian mummy, a visitor favourite, with an interactive display on Pahat’s journey from Egypt to '
     'the Berkshires.', None, RI, None, False),
    ('winged-victory', 'Objects and Their Stories', 'Winged Victory of Samothrace (cast)', 'Plaster reproduction', None,
     None, 'A full-size cast of the Louvre’s Nike of Samothrace, brought into the museum through the roof in 1910 and '
     'moved “centimetre by centimetre” to this floor in 2021. The museum says it is not going anywhere again.',
     None, RI, None, False),
    ('crane-room', 'Crane Room', 'Ellen Crane Memorial Room', 'Gallery', None, None,
     'The grand room named for Ellen Crane, used for shows and events; visitors pass through it on the way to Objects '
     'and Their Stories.', None, RI, None, False),
]
WHERE = {
    'Galleries 206-208': 'The museum lists the show in Galleries 206–208; where those rooms are on the second floor is '
                         'approximate.',
    'Objects and Their Stories': 'On the second floor since 2021; the room’s position on the map is approximate.',
    'Crane Room': 'On the second floor; the room’s position on the map is approximate.',
    'Entry': 'Outside, on the front lawn on South Street.',
}

# Collection: the museum's works on Google Arts & Culture (harvest_berkshire.py) and Commons, not known to be on view.
COMMONS_COLLECTION = [
    ('napoleon-mask', 'Death mask of Napoleon Bonaparte', None, None, 'Death mask of Napoleon Bonaparte.jpg'),
]


def gac_rows():
    f = CACHE / 'gac-works.json'
    if not f.exists():
        sys.exit('run tools/harvest_berkshire.py first')
    rows = []
    for w in json.loads(f.read_text()):
        w['gid'] = w['gac'].rsplit('/', 1)[1]
        rows.append(w)
    return rows


def year_of(date):
    m = re.search(r'\d{3,4}', date or '')
    return int(m[0]) if m else None


def build_works(floors):
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    works = []
    for key, room, title, artist, date, medium, text, pic, url, credit, temp in ON_VIEW:
        fl, gname = rooms[room]
        img = picture(f'berkshire-{key}', pic) if pic else None
        a = {'id': f'berkshire-{key}', 'title': title, 'artist': artist, 'date': date, 'medium': medium,
             'description': text, 'gallery': room, 'galleryName': gname, 'floor': fl,
             'placeNote': WHERE.get(room, 'Where the architects’ plan puts this gallery.'),
             'url': url, 'image': img,
             'imageCredit': (f'{credit}, via {COMMONS}' if credit else COMMONS) if img else None}
        if temp: a['temporary'] = True
        works.append({k: v for k, v in a.items() if v not in (None, '', [])})
    return {'source': 'Berkshire Museum: what is on view from reopening news and the architects’ press text; pictures '
                      'from Wikimedia Commons',
            'checked': time.strftime('%Y-%m-%d'), 'count': len(works), 'complete': False, 'artworks': works}


def clean_date(d):
    # Google Arts & Culture pads years ("0332") and gives ranges like "1866/1870"
    d = (d or '').replace('/', '–')
    return re.sub(r'\b0+(\d)', r'\1', d) or None


def build_guide(works):
    rows = []
    for a in works['artworks']:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a['artist'], 'date': a.get('date'),
                     'medium': a.get('medium'), 'url': a['url'], 'imageUrl': a.get('image'), 'onView': True,
                     'gallery': a['gallery'], 'floor': a['floor']}.items() if v not in (None, '')})
    for w in gac_rows():
        key = 'berkshire-gac-' + w['gid']
        date = clean_date(w['date'])
        if w['title'] == 'Cartonnage': date = None          # "0332" on the page: no usable date
        artist = w['artist'] if w['artist'] and w['artist'] != 'Unknown' else None
        rows.append({k: v for k, v in {'id': key, 'title': w['title'].replace('Compostion', 'Composition'),
                     'artist': artist, 'date': date, 'year': year_of(date), 'medium': w['type'] or w['medium'],
                     'description': (w['text'] or '').replace('\n', '').replace('  ', ' ')[:1200] or None,
                     'url': w['gac'], 'imageUrl': picture(key, w['image'] and ('url', w['image'] + '=w1000')),
                     'onView': False}.items() if v not in (None, '')})
    for key, title, artist, date, pic in COMMONS_COLLECTION:
        rows.append({k: v for k, v in {'id': f'berkshire-{key}', 'title': title, 'artist': artist, 'date': date,
                     'url': 'https://commons.wikimedia.org/wiki/File:' + urllib.parse.quote(pic.replace(' ', '_')),
                     'imageUrl': picture(f'berkshire-{key}', ('commons', pic)), 'onView': False}.items()
                     if v not in (None, '')})
    return {'museum': MUSEUM, 'name': NAME, 'checked': time.strftime('%Y-%m-%d'),
            'source': 'Berkshire Museum: reopening news (2026); its Google Arts & Culture pages; Wikimedia Commons',
            'onViewKnown': True,
            'note': 'The Berkshire Museum has no open online collection, and its website asks AI tools not to read it, '
                    'so this list is built from news of the 2026 reopening, the architects’ description of the new '
                    'galleries and the museum’s own Google Arts & Culture pages. The galleries and the Brooklyn Museum '
                    'show are on view now. The art at the end belongs to the museum but may not be on view (the '
                    'Cabinets of Curiosities and Objects and Their Stories rotate).',
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
