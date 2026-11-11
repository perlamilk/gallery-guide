#!/usr/bin/env python3
"""Build the Davis Museum at Wellesley College map guide (run: python3 tools/harvest_davis.py, then this).

    data/davis/floors.json       the five public floors seen from above (a flat 2D plan)
    data/davis/artworks.json     the works we know of, in the gallery for their period
    data/davis/images/           pictures from Google Arts & Culture, made smaller for phones
    data/guides/Q15694044.json   the same works, for the museum page

The map is approximate. The Davis hands out a paper gallery map at the front desk but publishes no floor plan, so
the floors are drawn by hand inside the building's real outline (OpenStreetMap way 43360020, traced by MassGIS from
2008 aerial photos), turned 17° so its walls run straight on the screen. Units are decimetres. What sits on each
floor comes from the museum's own words:
  - wellesley.edu/davismuseum/about/building: four floors of galleries around one staircase and a skylit void;
    "take the elevator up to … floor 5; walk down through the permanent collections galleries, on floors 4 and 2;
    … the Study Gallery and … temporary exhibitions on 2; and don't miss the Lower Level galleries!"; the Collins
    Cinema (168 seats) and Collins Café are in the same building;
  - the museum's 2016 press release for the reinstallation ("The Davis. Rediscovered"): level 2 holds the Ancient
    Mediterranean (with the Antioch mosaic set as a floor), Ancient Americas, South Asia, East Asia, Oceania and
    Africa, the Study Gallery, "Wellesley Collects", the Levine Works on Paper Gallery and the Friends of Art
    Gallery; level 4 Medieval, Renaissance, Southern and Northern Baroque, Spanish Colonial, Rococo, British
    portraits, Colonial American and 19th-century art; level 5 modern and contemporary art (rehung Feb 2026);
    the Lower Level temporary exhibitions;
  - visit and accessibility pages: front door up a set of steps from the plaza, ramp access along the side of the
    building, accessible restrooms in the museum and the café, bags larger than 11" x 15" checked at the front desk.
Floor 3 holds no galleries (offices and the print study room), so it isn't drawn.

The works: the Davis owns about 11,000. Its collection site (davis.emuseum.com) refuses cloud machines, so the works
come from the Davis's own pages on Google Arts & Culture (tools/harvest_davis.py), Wikidata (CC0) and the pages of the
current shows. None of these say whether a work is on view (except the current shows), so each work is put in the
gallery for its period and origin, and says so.
"""
import io
import json
import re
import subprocess
import sys
import time
import unicodedata
import urllib.parse
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'davis'
CACHE = ROOT / '.cache' / 'davis'
MUSEUM = 'Q15694044'
NAME = 'Davis Museum at Wellesley College'
SITE = 'https://www.wellesley.edu/davismuseum'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
APPROX = 'Approximate layout'
# The floors are traced from the Davis's own floor plans in its Bloomberg Connects guide (read Nov 11 2026). Each
# floor is drawn in the pixels of its own plan picture; FRAME turns them into one frame (the floor-4 plan) so the
# staircase and elevator line up from floor to floor: X = 95 + (x - x0)·s, Y = 143 + (y - y0)·s.
FRAME = {'LL': (107, 152, 1.053), '1': (330, 166, 1.571), '2': (332, 180, 1.571), '4': (95, 143, 1.0),
         '5': (107, 152, 1.053)}


def tp(fid, x, y):
    x0, y0, s = FRAME[fid]
    return [round((95 + (x - x0) * s + 320) * 1.7, 1), round((143 + (y - y0) * s - 100) * 1.7, 1)]


def box(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


# (id, kind, name, poly, label for galleries, holes)
ROOMS = {
    'LL': [
        ('Lower Level Galleries', 'gallery', 'Lower Level: Temporary Exhibitions', box(105, 152, 592, 555),
         'Temporary Exhibitions', [box(185, 378, 515, 437)]),
        ('LL-stair', 'corridor', 'Staircase', box(185, 378, 515, 437), None, None),
        ('LL-lift', 'corridor', 'Elevator', [[592, 388], [665, 388], [665, 437], [707, 437], [707, 490], [592, 490]],
         None, None),
    ],
    '1': [
        ('Lobby', 'corridor', 'Main Lobby · front desk',
         [[330, 350], [738, 350], [738, 433], [598, 433], [598, 608], [538, 608], [538, 433], [330, 433]], None, None),
        ('1-stair', 'corridor', 'Staircase and elevator',
         [[330, 307], [648, 307], [648, 315], [720, 315], [720, 350], [330, 350]], None, None),
        ('1-restrooms', 'space', 'Restrooms', box(598, 540, 685, 608), None, None),
        ('1-passage', 'corridor', 'Passage to the Collins Cinema & Café', box(270, 372, 330, 410), None, None),
        ('Collins Café', 'space', 'Collins Cinema & Café',
         [[82, 280], [218, 233], [248, 307], [277, 307], [270, 433], [125, 433]], None, None),
    ],
    '2': [
        ('Asian Art', 'gallery', 'Asian', [[332, 180], [445, 180], [445, 270], [385, 270], [385, 368], [332, 368]],
         'Asian', None),
        ('Ancient Mediterranean', 'gallery', 'Ancient Mediterranean · the Antioch mosaic, set in the floor',
         [[445, 180], [548, 180], [548, 270], [610, 270], [610, 325], [385, 325], [385, 270], [445, 270]],
         'Ancient Mediterranean', None),
        ('Ancient Americas', 'gallery', 'Ancient Americas', box(548, 180, 658, 270), 'Ancient Americas', None),
        ('Study Gallery', 'gallery', 'Study Gallery (chosen by faculty each semester)', box(658, 193, 738, 280),
         'Study Gallery', None),
        ('2-hall', 'corridor', 'Staircase', [[385, 325], [610, 325], [610, 270], [658, 270], [658, 368], [385, 368]],
         None, None),
        ('African Art', 'gallery', 'African', box(332, 368, 553, 452), 'African', None),
        ('Wellesley Method', 'gallery', 'Wellesley Method', box(553, 368, 625, 452), 'Wellesley Method', None),
        ('2-lift', 'corridor', 'Elevator', [[658, 330], [720, 330], [720, 368], [738, 368], [738, 400], [658, 400]],
         None, None),
        ('2-passage', 'corridor', 'Passage to the Print Study', box(625, 400, 658, 555), None, None),
        ('Print Study', 'gallery', 'Print Study (works on paper)',
         [[530, 555], [727, 555], [727, 598], [683, 598], [683, 610], [530, 610]], 'Print Study', None),
    ],
    '4': [
        ('18th Century', 'gallery', '18th-century European', box(95, 143, 229, 252), '18 C. European', None),
        ('Northern Baroque', 'gallery', '17th-century Northern Europe', box(229, 143, 350, 252), '17 C. Northern Europe',
         None),
        ('Southern Baroque', 'gallery', '17th-century Southern Europe', box(350, 143, 475, 252), '17 C. Southern Europe',
         None),
        ('Renaissance', 'gallery', '15th–16th-century European', box(475, 143, 607, 252), '15-16 C. European', None),
        ('Medieval', 'gallery', 'Medieval', box(607, 165, 727, 300), 'Medieval', None),
        ('Portraiture', 'gallery', 'Portraiture', box(95, 252, 180, 440), 'Portraiture', None),
        ('4-hall', 'corridor', 'Staircase and gallery walk',
         [[180, 252], [607, 252], [607, 440], [180, 440], [180, 377], [527, 377], [527, 303], [180, 303]], None, None),
        ('4-void', 'space', 'Open to the floor below', box(180, 303, 527, 377), None, None),
        ('Early American', 'gallery', 'Early American', box(95, 440, 229, 567), 'Early American', None),
        ('US Landscapes', 'gallery', '19th-century U.S. Landscapes', box(229, 440, 485, 505), '19 C. U.S. Landscapes',
         None),
        ('Native American', 'gallery', '19th–21st-century Native American', box(229, 505, 372, 567),
         '19-21 C. Native American', None),
        ('19th Century', 'gallery', '19th-century European & American',
         [[485, 440], [607, 440], [607, 567], [372, 567], [372, 505], [485, 505]], '19 C. European & American', None),
        ('4-lift', 'corridor', 'Elevator', [[607, 390], [685, 390], [685, 440], [727, 440], [727, 500], [607, 500]],
         None, None),
    ],
    '5': [
        ('Modern & Contemporary', 'gallery', 'Modern and Contemporary', box(107, 152, 593, 555),
         'Modern and Contemporary', [box(187, 305, 517, 375)]),
        ('5-void', 'space', 'Open to the floor below', box(187, 305, 517, 375), None, None),
        ('Contemporary East', 'gallery', 'Modern and Contemporary (east room)', box(593, 172, 708, 300),
         'Modern and Contemporary', None),
        ('5-lift', 'corridor', 'Elevator', [[593, 388], [665, 388], [665, 437], [708, 437], [708, 490], [593, 490]],
         None, None),
    ],
}

LABEL_AT = {'Lower Level Galleries': (350, 250), 'Modern & Contemporary': (350, 250)}   # off the stair well

DOORS = {
    'LL': [('LL-stair', 'Lower Level Galleries', (350, 437)), ('LL-lift', 'Lower Level Galleries', (592, 462))],
    '1': [('Lobby', '1-stair', (498, 350)), ('Lobby', '1-stair', (690, 350)), ('Lobby', '1-restrooms', (598, 585)),
          ('Lobby', '1-passage', (330, 391)), ('1-passage', 'Collins Café', (272, 391))],
    '2': [('Asian Art', 'Ancient Mediterranean', (445, 195)), ('Ancient Mediterranean', 'Ancient Americas', (548, 195)),
          ('Ancient Americas', '2-hall', (630, 270)), ('Ancient Americas', 'Study Gallery', (658, 258)),
          ('Asian Art', '2-hall', (385, 346)), ('Asian Art', 'African Art', (358, 368)),
          ('2-hall', 'Wellesley Method', (615, 368)), ('African Art', 'Wellesley Method', (553, 380)),
          ('2-hall', '2-lift', (658, 348)), ('2-lift', '2-passage', (642, 400)),
          ('Wellesley Method', '2-passage', (625, 425)), ('2-passage', 'Print Study', (642, 555))],
    '4': [('18th Century', 'Portraiture', (137, 252)), ('18th Century', 'Northern Baroque', (229, 165)),
          ('Northern Baroque', '4-hall', (260, 252)), ('Southern Baroque', '4-hall', (440, 252)),
          ('Southern Baroque', 'Renaissance', (475, 165)), ('Renaissance', '4-hall', (570, 252)),
          ('Renaissance', 'Medieval', (607, 270)), ('Portraiture', '4-hall', (180, 410)),
          ('Portraiture', 'Early American', (137, 440)), ('Early American', 'US Landscapes', (229, 465)),
          ('US Landscapes', 'Native American', (300, 505)), ('US Landscapes', '19th Century', (485, 465)),
          ('Native American', '19th Century', (372, 508)), ('4-hall', '19th Century', (567, 440)),
          ('4-hall', '4-lift', (607, 415))],
    '5': [('Modern & Contemporary', 'Contemporary East', (593, 256)), ('Modern & Contemporary', '5-lift', (593, 412))],
}

AMENITIES = {
    'LL': [('elevator', 618, 412), ('stairs', 350, 407)],
    '1': [('entrance', 738, 390), ('info', 630, 410), ('coat', 578, 485), ('restroom', 640, 585),
          ('elevator', 672, 332), ('stairs', 498, 328), ('dining', 183, 375)],
    '2': [('elevator', 672, 348), ('stairs', 497, 346)],
    '4': [('elevator', 632, 415), ('stairs', 358, 410)],
    '5': [('elevator', 618, 412), ('stairs', 352, 408)],
}
LABELS = {
    'LL': [],
    '1': [('Front door up a few steps from the plaza; ramp along the side of the building', 'note', 640, 650),
          ('Accessible restrooms in the museum and the café', 'note', 200, 470)],
    '2': [('Floor 3: offices (no galleries)', 'note', 420, 520)],
    '4': [],
    '5': [('Saw-tooth skylights', 'note', 350, 230)],
}
FLOORS = [
    ('LL', 'Lower Level', 'Temporary exhibitions: Excavating Antioch · Shi: Stories in Stone', 0),
    ('1', 'Floor 1', 'Entrance · Main Lobby and front desk · Coat check · Restrooms · Collins Cinema & Café', 1),
    ('2', 'Floor 2', 'Asian · Ancient Mediterranean · Ancient Americas · African · Wellesley Method · Study Gallery · '
                     'Print Study', 2),
    ('4', 'Floor 4', 'Medieval · 15th–18th-century European · Portraiture · Early American · 19th century · '
                     'Native American', 4),
    ('5', 'Floor 5', 'Modern and Contemporary art under the skylights', 5),
]


def build_floors():
    floors = []
    for fid, label, area, order in FLOORS:
        rooms = []
        for rid, kind, name, poly, short, holes in ROOMS[fid]:
            r = {'id': rid, 'kind': kind, 'name': name, 'poly': [tp(fid, *q) for q in poly]}
            if kind == 'gallery': r['label'] = short or rid
            if holes: r['holes'] = [[tp(fid, *q) for q in h] for h in holes]
            if rid in LABEL_AT: r['labelAt'] = tp(fid, *LABEL_AT[rid])
            rooms.append(r)
        ids = {r['id'] for r in rooms}
        doors = [{'a': a, 'b': b, 'at': tp(fid, x, y), 'width': 24, 'axis': 'o'} for a, b, (x, y) in DOORS[fid]]
        for d in doors:
            assert d['a'] in ids and d['b'] in ids, (fid, d)
        floors.append({'id': fid, 'label': label, 'area': area, 'order': order, 'transform': [1, 0, 0],
                       'rooms': rooms, 'closed': [],
                       'amenities': [{'type': t, 'at': tp(fid, x, y)} for t, x, y in AMENITIES[fid]],
                       'labels': [{'text': t, 'kind': k, 'at': tp(fid, x, y)} for t, k, x, y in LABELS[fid]],
                       'doors': doors})
    return {'about': 'Built by tools/build_davis.py. Rooms traced from the Davis’s own floor plans in its Bloomberg '
                     'Connects guide (Nov 2026). Which gallery a work is in is guessed from its date and origin.',
            'source': 'Davis Museum floor plans in its Bloomberg Connects guide (Nov 2026); Davis Museum website',
            'units': 'plan units', 'defaultFloor': '1', 'galleryWord': 'Gallery', 'floors': floors}


# ---- works ------------------------------------------------------------------------------------------------------

# The current shows, from their pages on the Davis's website (Sept 25, 2026 – May 30, 2027). The museum doesn't say
# which galleries they fill; special exhibitions are on the Lower Level.
SHOWS = {
    'excavating-antioch-the-archaeology-of-an-ancient-city':
        'Excavating Antioch: The Archaeology of an Ancient City (Sep 25, 2026 – May 30, 2027)',
    'shi-stories-in-stone': 'Shi: Stories in Stone (Sep 25, 2026 – May 30, 2027)',
}
SHOW_WORKS = [
    ('shi-stories-in-stone', 'lock-up-screens-web-shi.jpg', 'China', 'Ying Stone in the Form of Spiraling Incense Smoke',
     'Modern period, 20th century', 'Limestone from Yingde county, Guangdong province, 20th-century wooden stand, '
     'Southern openwork style', 'Gift of Alan Helms', '2024.15.7a-b'),
    ('excavating-antioch-the-archaeology-of-an-ancient-city', 'lock-up-screens-web-antioch-new.jpg', 'Roman',
     'Marble feet', '', 'Marble', 'Antioch Excavation Collection, Department of Art and Archaeology, Princeton University '
     '(lent to the exhibition)', 'A-005746'),
]

ASIA = r'\b(chin|japan|korea|india|tibet|nepal|thai|vietnam|cambod|burm|indones|asia|mughal|pakistan|edo period|meiji|' \
       r'qing|ming dynasty|song dynasty|tang dynasty|han dynasty|ukiyo|hiroshige|hokusai|kuniyoshi|yoshitoshi|' \
       r'chikanobu|kunisada)'
AFRICA = r'afric|nigeria|congo|yoruba|benin|ghana|mali|kenya|ethiop|ivory coast|cameroon|oceani|papua|new guinea|' \
         r'maori|polynes|melanes|pre-columbian|precolumbian|maya|aztec|olmec|inca|peru|moche|nazca|colima|nayarit|' \
         r'mesoamerica|ancient americas|costa rica|zapotec|veracruz'
ANCIENT = r'roman|greek|egypt|etrus|antioch|mesopotam|assyr|sumer|cypr|byzant|hellenist|attic|corinth|mosaic|' \
          r'babylon|achaemenid|sassan|phoenic'
PAPER = r'photograph|albumen|daguerreo|tintype|ambrotype|carte de visite|gelatin silver|mezzotint|engraving|etching|' \
        r'lithograph|woodcut|drawing|print\b|aquatint|watercolor on paper|ink on paper|graphite|chalk'
SOUTH = r'ital|spain|spanish|portug|mexic|peru|bolivia|colombia|ecuador|latin america|new spain|guatemal|venet|' \
        r'florent|siena|bologna|naples|neapolit|roma(?!n)|sevill|madrid'
NORTH_B = r'dutch|flemish|netherland|german|british|english|french|american|colonial|scottish|belgian'


def norm(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '', s)


def year_of(date):
    d = (date or '').lower()
    bce = bool(re.search(r'\b(b\.?c\.?e?|bc)\b', d))
    m = re.search(r'(\d{3,4})', d)
    if m and not re.search(r'century', d[:m.start()] + d[m.end():m.end() + 10]):
        y = int(m[1])
        return -y if bce else y
    m = re.search(r'(\d+)(?:st|nd|rd|th)[^,;]*?century', d)
    if m:
        c = int(m[1])
        return -(c - 1) * 100 - 50 if bce else (c - 1) * 100 + 50
    m = re.search(r'\b(\d{1,3})\b', d)
    if m and bce: return -int(m[1])
    return None


AMERICAS = r'pre-columbian|precolumbian|maya|aztec|olmec|inca|peru|moche|nazca|colima|nayarit|mesoamerica|' \
           r'ancient americas|costa rica|zapotec|veracruz|teotihuacan|chancay|chimu|wari'
NATIVE = r'native american|navajo|hopi|pueblo|lakota|sioux|cherokee|apache|zuni|acoma|tlingit|haida|inuit|ojibwe|' \
         r'cheyenne|kiowa|first nations'
PORTRAIT = r'portrait|self-portrait|\bbust of\b'
LANDSCAPE = r'landscape|valley|river|mountain|lake|view of|hudson|niagara|white mountains|sunset|coast'
AMERICAN = r'american|united states|\bu\.s\.|boston|new york|massachusetts|hudson river|colonial'


def place(w):
    """The gallery for a work, from its date, origin and medium."""
    hay = ' '.join([w.get('title', ''), w.get('artist', ''), w.get('medium', ''), w.get('type', ''),
                    w.get('origin', ''), w.get('text', '')[:400]]).lower()
    y = w.get('year')
    if re.search(ANCIENT, hay) and (y is None or y < 700): return 'Ancient Mediterranean'
    if re.search(NATIVE, hay) and (y is None or y >= 1800): return 'Native American'
    if re.search(AMERICAS, hay) and (y is None or y < 1600): return 'Ancient Americas'
    if y is not None and y < 0: return 'Ancient Mediterranean'
    if re.search(ASIA, hay): return 'Asian Art'
    if re.search(AFRICA, hay): return 'African Art'
    if re.search(PAPER, hay): return 'Print Study'
    if y is None: return 'Study Gallery'
    if y < 500: return 'Ancient Mediterranean'
    if y < 1400: return 'Medieval'
    if y < 1600: return 'Renaissance'
    if y < 1900 and re.search(PORTRAIT, hay) and not re.search(AMERICAN, hay): return 'Portraiture'
    if y < 1800 and re.search(AMERICAN, hay): return 'Early American'
    if y < 1700: return 'Southern Baroque' if re.search(SOUTH, hay) and not re.search(NORTH_B, hay) else 'Northern Baroque'
    if y < 1800: return '18th Century'
    if y < 1900: return 'US Landscapes' if re.search(AMERICAN, hay) and re.search(LANDSCAPE, hay) else '19th Century'
    return 'Modern & Contemporary'


def build_works(floors):
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    out, seen = [], set()

    def add(a, room, note):
        floor, gname = rooms[room]
        a.update({'gallery': room, 'galleryName': gname, 'floor': floor, 'placeNote': note})
        out.append({k: v for k, v in a.items() if v not in (None, '')})
        seen.add(norm(a['title']) + norm(a.get('artist'))[:8])
        if a.get('accession'): seen.add(a['accession'])

    for show, img, artist, title, date, medium, credit, acc in SHOW_WORKS:
        key = 'davis-' + norm(title)[:30]
        add({'id': key, 'title': title, 'artist': artist, 'date': date, 'year': year_of(date), 'medium': medium,
             'accession': acc, 'creditLine': credit, 'exhibition': SHOWS[show], 'onView': True,
             'url': f'{SITE}/art/exhibitions/{show}',
             'image': picture(key, f'https://wellesley-college.transforms.svdcdn.com/production/davismuseum/{img}?w=1200'),
             'imageCredit': 'Davis Museum at Wellesley College'},
            'Lower Level Galleries', 'On view in this show. The museum doesn’t say which Lower Level gallery it is in.')

    guessed = ('Gallery guessed from the work’s date and origin: the Davis doesn’t publish what is on view, so this '
               'work may be in storage.')
    for w in gac():
        if not w['title'] or norm(w['title']) + norm(w['artist'])[:8] in seen: continue
        key = 'davis-gac-' + w['gac'].rsplit('/', 1)[1]
        a = {'id': key, 'title': w['title'], 'artist': w['artist'] or 'Unknown artist', 'date': w['date'],
             'year': year_of(w['date']), 'medium': w['medium'], 'type': w['type'], 'accession': w.get('accession'),
             'creditLine': w['credit'], 'dimensions': w['dimensions'], 'description': w['text'][:1200] or None,
             'origin': w['place'], 'url': w['gac'], 'image': picture(key, w['image'] and w['image'] + '=w1000'),
             'imageCredit': 'Davis Museum at Wellesley College, via Google Arts & Culture'}
        hint = {'Photography': 'photograph', 'Mezzotints': 'mezzotint', 'Antioch': 'antioch'}
        story = next((v for k, v in hint.items() if k in w.get('story', '')), '')
        add(a, place({**a, 'text': w['text'] + ' ' + story}), guessed)
    for w in wikidata():
        if (w['accession'] and w['accession'] in seen) or norm(w['title']) + norm(w['artist'])[:8] in seen: continue
        img = None
        if w['image']:
            img = 'https://commons.wikimedia.org/wiki/Special:FilePath/' + \
                  urllib.parse.quote(urllib.parse.unquote(w['image'].rsplit('/', 1)[1])) + '?width=800'
        a = {'id': 'davis-' + w['qid'], 'title': w['title'], 'artist': w['artist'], 'date': w['date'],
             'year': year_of(w['date']), 'medium': w['medium'], 'type': w['type'], 'origin': w['origin'],
             'roughYear': None if year_of(w['date']) or not w['born'] else w['born'] + 35,
             'accession': w['accession'], 'url': w['url'] or f'https://www.wikidata.org/wiki/{w["qid"]}',
             'wikidata': w['qid'], 'image': img, 'imageCredit': 'Wikimedia Commons' if img else None}
        add(a, place({**a, 'year': a['year'] or a.pop('roughYear', None)}), guessed)
    for a in out:
        a.pop('origin', None); a.pop('roughYear', None)
    order = {r['id']: i for f in floors['floors'] for i, r in enumerate(f['rooms'])}
    forder = {f['id']: f['order'] for f in floors['floors']}
    out.sort(key=lambda a: (-forder[a['floor']], order[a['gallery']], a.get('year') or 0))
    return {'source': 'Davis Museum pages on Google Arts & Culture, Wikidata (CC0) and the Davis website; galleries '
                      'guessed from date and origin', 'checked': time.strftime('%Y-%m-%d'), 'count': len(out),
            'complete': False, 'artworks': out}


def build_guide(works):
    rows = []
    for a in works['artworks']:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a['artist'], 'date': a.get('date'),
                     'year': a.get('year'), 'medium': a.get('medium'), 'accession': a.get('accession'),
                     'url': a['url'], 'imageUrl': a.get('image'), 'onView': bool(a.get('onView')),
                     'gallery': a['gallery'], 'floor': a['floor']}.items() if v not in (None, '')})
    rows.sort(key=lambda w: (not w['onView'], norm(w.get('artist', '')), w.get('year') or 0))
    return {'museum': MUSEUM, 'name': 'Davis Museum and Cultural Center', 'checked': time.strftime('%Y-%m-%d'),
            'source': 'Davis Museum on Google Arts & Culture, Wikidata and the Davis website', 'onViewKnown': False,
            'note': 'The Davis owns about 11,000 works. This list is what it shows on Google Arts & Culture, the Davis '
                    'works in Wikidata and the current shows. Only the works in current shows are known to be on view.',
            'works': rows}


# rooms of the earlier, approximate map
OLD = {'Medieval & Renaissance': 'Renaissance', 'Works on Paper Gallery': 'Print Study',
       'Africa, Oceania & the Americas': 'African Art', 'Friends of Art Gallery': 'Study Gallery',
       'Lower Level East': 'Lower Level Galleries'}


def floors_only(floors):
    """Redraw the map and move the saved works onto it, without the harvest caches."""
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    path = OUT / 'artworks.json'
    works = json.loads(path.read_text())
    for a in works['artworks']:
        g = 'Lower Level Galleries' if a.get('onView') else place({**a, 'text': a.get('description', '')})
        if g == 'Study Gallery': g = OLD.get(a['gallery'], a['gallery'] if a['gallery'] in rooms else g)   # undated: keep the room the artist's dates gave
        a['gallery'], (a['floor'], a['galleryName']) = g, rooms[g]
    order = {r['id']: i for f in floors['floors'] for i, r in enumerate(f['rooms'])}
    forder = {f['id']: f['order'] for f in floors['floors']}
    works['artworks'].sort(key=lambda a: (-forder[a['floor']], order[a['gallery']], a.get('year') or 0))
    path.write_text(json.dumps(works, ensure_ascii=False, separators=(',', ':')))
    gpath = ROOT / 'data' / 'guides' / f'{MUSEUM}.json'
    guide = json.loads(gpath.read_text())
    where = {a['id']: (a['gallery'], a['floor']) for a in works['artworks']}
    for w in guide['works']:
        if w['id'] in where: w['gallery'], w['floor'] = where[w['id']]
    gpath.write_text(json.dumps(guide, ensure_ascii=False, separators=(',', ':')))
    by = {}
    for a in works['artworks']: by[a['gallery']] = by.get(a['gallery'], 0) + 1
    print(by)


def main():
    OUT.mkdir(exist_ok=True)
    floors = build_floors()
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    if sys.argv[1:2] == ['--floors-only']: return floors_only(floors)
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
    print(f'{works["count"]} works on the map, {sum("image" in a for a in works["artworks"])} with pictures')
    for k, v in by.items(): print(f'  {k}: {v}')


if __name__ == '__main__':
    sys.exit(main())
