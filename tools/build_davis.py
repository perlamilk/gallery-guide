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
K = 2          # drawn in decimetres, stored at twice that so labels fit like other museums' maps


def pt(x, y):
    return [x * K, y * K]


def rect(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


# The building (decimetres): the museum's main block, with its south-east corner cut out for the entrance plaza,
# and the lower wing on the south side with the Collins Café and Cinema.
MAIN = [[6, 11], [433, 11], [433, 195], [245, 195], [245, 316], [6, 316]]
NORTH = rect(6, 11, 433, 195)        # the tall block under the saw-tooth skylights (floors 4 and 5)
STAIR = rect(215, 11, 265, 195)      # the maple-panelled staircase that rises through every floor, with the elevator
VOID = rect(150, 60, 215, 150)       # the skylit void, open from floor 2 up to the roof
ELEV, STAIRS = (240, 175), (240, 90)

# (id, kind, name, poly, label for galleries)
ROOMS = {
    'LL': [
        ('Lower Level Galleries', 'gallery', 'Lower Level Galleries: special exhibitions',
         [[6, 11], [215, 11], [215, 195], [245, 195], [245, 316], [6, 316]], 'Special Exhibitions'),
        ('Lower Level East', 'gallery', 'Lower Level Galleries (east)', rect(265, 11, 433, 195), 'Special Exhibitions'),
        ('LL-stair', 'corridor', 'Staircase and elevator', STAIR, None),
    ],
    '1': [
        ('Lobby', 'corridor', 'Lobby · front desk · bag check', [[140, 195], [245, 195], [245, 316], [140, 316]], None),
        ('1-stair', 'corridor', 'Staircase and elevator', STAIR, None),
        ('Collins Café', 'space', 'Collins Café', rect(55, 316, 250, 420), None),
        ('Collins Cinema', 'space', 'Collins Cinema (168 seats: films and talks)', [[55, 420], [250, 420], [250, 586], [85, 586]], None),
        ('1-staff-n', 'corridor', 'Staff areas (not open to visitors)', [[6, 11], [215, 11], [215, 195], [140, 195], [140, 316], [6, 316]], None),
        ('1-staff-e', 'corridor', 'Staff areas (not open to visitors)', rect(265, 11, 433, 195), None),
    ],
    '2': [
        ('Ancient Mediterranean', 'gallery', 'Ancient Mediterranean · the Antioch mosaic, set in the floor',
         [[6, 11], [150, 11], [150, 195], [6, 195]], 'Ancient World'),
        ('Wellesley Collects', 'gallery', 'Wellesley Collects', rect(150, 11, 215, 60), 'Wellesley Collects'),
        ('2-void', 'space', 'Skylit atrium: look up to the roof', VOID, None),
        ('Asian Art', 'gallery', 'South Asia · East Asia', rect(265, 11, 433, 100), 'Asia'),
        ('Africa, Oceania & the Americas', 'gallery', 'Africa · Oceania · Ancient Americas', rect(265, 100, 433, 195),
         'Africa · Americas'),
        ('Study Gallery', 'gallery', 'Study Gallery (chosen by faculty each semester)', rect(6, 195, 100, 316), 'Study Gallery'),
        ('Works on Paper Gallery', 'gallery', 'Morelle Lasky Levine ’56 Works on Paper Gallery', rect(100, 195, 170, 316),
         'Works on Paper'),
        ('Friends of Art Gallery', 'gallery', 'Friends of Art Gallery (changing exhibitions)', rect(170, 195, 245, 316),
         'Friends of Art'),
        ('2-hall', 'corridor', 'Gallery walk around the atrium', rect(150, 150, 215, 195), None),
        ('2-stair', 'corridor', 'Staircase and elevator', STAIR, None),
    ],
    '4': [
        ('Medieval & Renaissance', 'gallery', 'Medieval · Renaissance', [[6, 11], [150, 11], [150, 195], [6, 195]],
         'Medieval · Renaissance'),
        ('Southern Baroque', 'gallery', 'Southern Baroque · Spanish Colonial', rect(265, 11, 433, 100),
         'Southern Baroque'),
        ('Northern Baroque', 'gallery', 'Northern Baroque · Rococo · British portraits · Colonial American',
         rect(265, 100, 433, 195), 'Northern Baroque'),
        ('19th Century', 'gallery', '19th century: American landscapes, Native American, European and American art',
         rect(6, 195, 245, 316), '19th Century'),
        ('4-balcony', 'space', 'Balcony over the skylit atrium', VOID, None),
        ('4-hall', 'corridor', 'Gallery walk', [[150, 11], [215, 11], [215, 60], [150, 60]], None),
        ('4-hall-s', 'corridor', 'Gallery walk', rect(150, 150, 215, 195), None),
        ('4-stair', 'corridor', 'Staircase and elevator', STAIR, None),
    ],
    '5': [
        ('Modern & Contemporary', 'gallery', 'Modern and contemporary art, under the saw-tooth skylights',
         [[6, 11], [215, 11], [215, 195], [6, 195]], 'Modern · Contemporary'),
        ('Contemporary East', 'gallery', 'Contemporary art (east)', rect(265, 11, 433, 195), 'Contemporary'),
        ('5-stair', 'corridor', 'Staircase and elevator', STAIR, None),
    ],
}

DOORS = {
    'LL': [('LL-stair', 'Lower Level Galleries', (215, 120)), ('LL-stair', 'Lower Level East', (265, 120))],
    '1': [('Lobby', '1-stair', (240, 195)), ('Lobby', 'Collins Café', (200, 316))],
    '2': [('2-stair', 'Asian Art', (265, 55)), ('2-stair', 'Africa, Oceania & the Americas', (265, 150)),
          ('2-stair', '2-hall', (215, 172)), ('2-hall', 'Ancient Mediterranean', (150, 172)),
          ('2-hall', 'Friends of Art Gallery', (195, 195)), ('Friends of Art Gallery', 'Works on Paper Gallery', (170, 255)),
          ('Works on Paper Gallery', 'Study Gallery', (100, 255)), ('Ancient Mediterranean', 'Wellesley Collects', (150, 35)),
          ('Asian Art', 'Africa, Oceania & the Americas', (350, 100)), ('2-hall', '2-void', (182, 150))],
    '4': [('4-stair', 'Southern Baroque', (265, 55)), ('4-stair', 'Northern Baroque', (265, 150)),
          ('4-stair', '4-hall-s', (215, 172)), ('4-stair', '4-hall', (215, 35)),
          ('4-hall', 'Medieval & Renaissance', (150, 35)), ('4-hall-s', 'Medieval & Renaissance', (150, 172)),
          ('4-hall-s', '19th Century', (182, 195)), ('Southern Baroque', 'Northern Baroque', (350, 100)),
          ('4-hall-s', '4-balcony', (182, 150))],
    '5': [('5-stair', 'Modern & Contemporary', (215, 120)), ('5-stair', 'Contemporary East', (265, 120))],
}

AMENITIES = {
    'LL': [('elevator', *ELEV), ('stairs', *STAIRS)],
    '1': [('entrance', 245, 255), ('info', 205, 240), ('coat', 165, 240), ('restroom', 165, 290), ('elevator', *ELEV),
          ('stairs', *STAIRS), ('dining', 150, 365), ('restroom', 90, 400)],
    '2': [('elevator', *ELEV), ('stairs', *STAIRS)],
    '4': [('elevator', *ELEV), ('stairs', *STAIRS)],
    '5': [('elevator', *ELEV), ('stairs', *STAIRS)],
}
LABELS = {
    'LL': [(APPROX, 'note', 220, 340)],
    '1': [('Front door up a few steps from the plaza; ramp along the side of the building', 'note', 340, 270),
          ('Accessible restrooms in the museum and the café', 'note', 340, 310), (APPROX, 'note', 340, 350)],
    '2': [('Floor 3: offices and print study room (no galleries)', 'note', 220, 345), (APPROX, 'note', 220, 375)],
    '4': [(APPROX, 'note', 220, 345)],
    '5': [('Saw-tooth skylights', 'note', 110, 60), (APPROX, 'note', 220, 225)],
}
FLOORS = [
    ('LL', 'Lower Level', 'Special exhibitions: Excavating Antioch · Shi: Stories in Stone', 0),
    ('1', 'Floor 1', 'Entrance · Lobby and front desk · Bag check · Restrooms · Collins Café · Collins Cinema', 1),
    ('2', 'Floor 2', 'Ancient Mediterranean · Asia · Africa, Oceania and the Americas · Study Gallery · '
                     'Works on Paper · Friends of Art Gallery · Wellesley Collects', 2),
    ('4', 'Floor 4', 'Medieval · Renaissance · Baroque · Spanish Colonial · Rococo · Colonial American · 19th century', 4),
    ('5', 'Floor 5', 'Modern and contemporary art under the skylights', 5),
]


def build_floors():
    floors = []
    for fid, label, area, order in FLOORS:
        rooms, closed = [], []
        for rid, kind, name, poly, short in ROOMS[fid]:
            if kind == 'closed':
                closed.append({'poly': [pt(*q) for q in poly]})
                continue
            r = {'id': rid, 'kind': kind, 'name': name, 'poly': [pt(*q) for q in poly]}
            if kind == 'gallery': r['label'] = short or rid
            rooms.append(r)
        ids = {r['id'] for r in rooms}
        doors = [{'a': a, 'b': b, 'at': pt(x, y), 'width': 24, 'axis': 'o'} for a, b, (x, y) in DOORS[fid]]
        for d in doors:
            assert d['a'] in ids and d['b'] in ids, (fid, d)
        floors.append({'id': fid, 'label': label, 'area': area, 'order': order, 'transform': [1, 0, 0],
                       'rooms': rooms, 'closed': closed,
                       'amenities': [{'type': t, 'at': pt(x, y)} for t, x, y in AMENITIES[fid]],
                       'labels': [{'text': t, 'kind': k, 'at': pt(x, y)} for t, k, x, y in LABELS[fid]],
                       'doors': doors})
    return {'about': 'Built by tools/build_davis.py. The layout is approximate: the Davis publishes no floor plan, so '
                     'the galleries are drawn inside the building’s real outline from the museum’s own description '
                     'of what is on each floor.',
            'source': 'Davis Museum website (building, visit and accessibility pages) and its 2016 reinstallation '
                      'press release; building outline from OpenStreetMap (MassGIS). Layout drawn by hand, approximate',
            'units': 'half-decimetres (1 unit = 5 cm)', 'defaultFloor': '1', 'galleryWord': 'Gallery', 'floors': floors}


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


def place(w):
    """(room, note) for a work, from its date, origin and medium."""
    hay = ' '.join([w.get('title', ''), w.get('artist', ''), w.get('medium', ''), w.get('type', ''),
                    w.get('origin', ''), w.get('text', '')[:400]]).lower()
    y = w.get('year')
    if re.search(ANCIENT, hay) and (y is None or y < 700): return 'Ancient Mediterranean'
    if y is not None and y < 0: return 'Ancient Mediterranean'
    if re.search(ASIA, hay): return 'Asian Art'
    if re.search(AFRICA, hay): return 'Africa, Oceania & the Americas'
    if re.search(PAPER, hay): return 'Works on Paper Gallery'
    if y is None: return 'Study Gallery'
    if y < 1600: return 'Medieval & Renaissance' if y >= 500 else 'Ancient Mediterranean'
    if y < 1800: return 'Southern Baroque' if re.search(SOUTH, hay) and not re.search(NORTH_B, hay) else 'Northern Baroque'
    if y < 1900: return '19th Century'
    return 'Modern & Contemporary'


def picture(key, url):
    """Download once (politely) and save a phone-sized JPEG; returns the app path."""
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
    return f'data/davis/images/{key}.jpg'


def wikidata():
    q = '''SELECT ?w ?title ?creator ?born ?nat ?date ?img ?acc ?material ?type ?origin ?url WHERE {
      ?w wdt:P195 wd:%s . OPTIONAL { ?w rdfs:label ?title FILTER(lang(?title)="en") }
      OPTIONAL { ?w wdt:P170 ?c . ?c rdfs:label ?creator FILTER(lang(?creator)="en")
                 OPTIONAL { ?c wdt:P569 ?born } OPTIONAL { ?c wdt:P27 ?n . ?n rdfs:label ?nat FILTER(lang(?nat)="en") } }
      OPTIONAL { ?w wdt:P571 ?date } OPTIONAL { ?w wdt:P18 ?img } OPTIONAL { ?w wdt:P973 ?url }
      OPTIONAL { ?w wdt:P31 ?t . ?t rdfs:label ?type FILTER(lang(?type)="en") }
      OPTIONAL { ?w wdt:P495 ?o . ?o rdfs:label ?origin FILTER(lang(?origin)="en") }
      OPTIONAL { ?w p:P217 ?s . ?s ps:P217 ?acc . ?s pq:P195 wd:%s }
      OPTIONAL { ?w wdt:P186 ?m . ?m rdfs:label ?material FILTER(lang(?material)="en") } }''' % (MUSEUM, MUSEUM)
    f = CACHE / 'wikidata.json'
    if not f.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        url = 'https://query.wikidata.org/sparql?format=json&query=' + urllib.parse.quote(q)
        out = subprocess.run(['curl', '-s', '-f', '-m', '120', '-A', UA, url], capture_output=True).stdout
        if not out: raise SystemExit('Wikidata did not answer')
        f.write_bytes(out)
    rows = {}
    for b in json.loads(f.read_text())['results']['bindings']:
        v = {k: x['value'] for k, x in b.items()}
        qid = v['w'].rsplit('/', 1)[1]
        r = rows.setdefault(qid, {'qid': qid, 'title': v.get('title') or '', 'artist': set(), 'date': '', 'image': None,
                                  'accession': '', 'medium': set(), 'type': '', 'origin': '', 'url': '', 'born': None,
                                  'nat': set()})
        if v.get('born') and not v['born'].startswith('-') and r['born'] is None: r['born'] = int(v['born'][:4])
        if v.get('nat'): r['nat'].add(v['nat'])
        if v.get('creator'): r['artist'].add(v['creator'])
        if v.get('material'): r['medium'].add(v['material'])
        if v.get('date'):
            yr = v['date'].split('-')[0] if not v['date'].startswith('-') else '-' + v['date'][1:].split('-')[0]
            r['date'] = str(int(yr)) if int(yr) > 0 else f'{-int(yr)} BCE'
        if v.get('img'): r['image'] = v['img']
        if v.get('acc'): r['accession'] = v['acc']
        if v.get('type'): r['type'] = r['type'] or v['type']
        if v.get('origin'): r['origin'] = r['origin'] or v['origin']
        if v.get('url') and 'emuseum' in v['url']: r['url'] = v['url']
    out = []
    for r in rows.values():
        if not r['title'] or re.fullmatch(r'Q\d+', r['title']): continue
        r['artist'] = ', '.join(sorted(r['artist'])) or 'Unknown artist'
        r['medium'] = ', '.join(sorted(r['medium']))
        r['origin'] = ' '.join([r['origin']] + sorted(r['nat'])).strip()
        out.append(r)
    return out


def gac():
    f = CACHE / 'gac-works.json'
    if not f.exists(): raise SystemExit('run tools/harvest_davis.py first')
    return json.loads(f.read_text())


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
    print(f'{works["count"]} works on the map, {sum("image" in a for a in works["artworks"])} with pictures')
    for k, v in by.items(): print(f'  {k}: {v}')


if __name__ == '__main__':
    sys.exit(main())
