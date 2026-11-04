#!/usr/bin/env python3
"""Build the Norman Rockwell Museum (Stockbridge, MA) map guide (run: python3 tools/harvest_nrm.py, then this).

    data/nrm/floors.json       the grounds, the Main Level and the Lower Level, seen from above (flat 2D)
    data/nrm/artworks.json     Rockwell's paintings and studies we know of, in the gallery where they likely hang
    data/nrm/images/           pictures from Google Arts & Culture, made smaller for phones
    data/guides/Q713204.json   the same works plus the museum's archive items, for the museum page

Where the information comes from
--------------------------------
nrm.org and the collection site (collection.nrm.org) answer 403 to cloud machines (a bot check), and the Internet
Archive's copies can't be reached from the cloud either, so the museum's own floor plan, if it publishes one, was not
seen. The map is APPROXIMATE and says so:

  - Grounds: OpenStreetMap (www.openstreetmap.org/api/0.6/map, cached in .cache/nrm/osm.xml): the museum building
    (way 216184574), Rockwell's Studio (216184517), Linwood House (216184547), the walks to the Studio (377980637) and
    past Linwood House (377980855), the drive to the front door (377980395), the parking lots (377981545, 940563368,
    940563369). Metres east/north of 42.2879 N, 73.3355 W, turned 17.5 degrees so the building's walls run straight
    up the page. The Housatonic River is to the east, down the hill.
  - The building (Robert A. M. Stern, 1993): its outline is OpenStreetMap's. What is inside comes from descriptions:
    the architects' and visitors' accounts say the galleries run in a line, with the octagonal Four Freedoms gallery
    in the middle under the lantern-shaped cupola, a cross-axis from it to the terrace and its view over the
    Housatonic valley, a front that faces a lawn "like a New England town green", galleries on the main floor and
    more one floor down ("start on the main floor or head down to the lower level"), and the Museum Store. Which room
    is the lobby, store, restrooms and elevator, and how the lower level is divided, are our guesses.
  - Exhibitions from the museum's announcements (Oct 2026): Exploring Calvin and Hobbes and the George Herriman /
    Krazy Kat installation, and Norman Rockwell: The Human Touch (Nov 14, 2026 – May 31, 2027), and Many Lights, One
    Season (Nov 20, 2026 – Feb 20, 2027). The Studio is open May to early November (closes Nov 8, 2026), the Terrace
    Café in summer.

The works: the museum owns 574 original works by Rockwell (and about 100,000 archive items). What can be read from
the cloud is the museum's own pages on Google Arts & Culture (tools/harvest_nrm.py) and Wikidata (CC0). Rockwell's
paintings and studies go on the map: the Four Freedoms in their gallery (the museum says they hang there), the
others in a main-floor Rockwell gallery by date, each saying it may be in storage. Archive photographs, letters and
tear sheets, and works by other illustrators, are listed on the museum page only.
"""
import io
import json
import math
import re
import subprocess
import sys
import time
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'nrm'
CACHE = ROOT / '.cache' / 'nrm'
MUSEUM = 'Q713204'
NAME = 'Norman Rockwell Museum'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
GUESS = '(approximate)'

# ---- the map ----------------------------------------------------------------------------------------------------

LAT0, LON0 = 42.2879, -73.3355
TURN = math.radians(-17.5)
KG = 3            # grounds: map units per metre
KB = 10           # building floors: map units per metre


def G(x, y):
    return [round((x + 210) * KG, 1), round((128 - y) * KG, 1)]


def B(x, y):
    return [round((x + 56) * KB, 1), round((42 - y) * KB, 1)]


def osm():
    f = CACHE / 'osm.xml'
    if not f.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        url = 'https://www.openstreetmap.org/api/0.6/map?bbox=-73.3420,42.2840,-73.3300,42.2920'
        out = subprocess.run(['curl', '-s', '-f', '-m', '90', '-A', UA, url], capture_output=True).stdout
        if not out: raise SystemExit('OpenStreetMap did not answer')
        f.write_bytes(out)
    root = ET.parse(f).getroot()
    nodes = {n.get('id'): (float(n.get('lat')), float(n.get('lon'))) for n in root.iter('node')}
    ways = {}
    for w in root.iter('way'):
        pts = []
        for nd in w.findall('nd'):
            lat, lon = nodes[nd.get('ref')]
            x, y = (lon - LON0) * 111320 * math.cos(math.radians(LAT0)), (lat - LAT0) * 110540
            pts.append((round(x * math.cos(TURN) - y * math.sin(TURN), 1), round(x * math.sin(TURN) + y * math.cos(TURN), 1)))
        ways[w.get('id')] = pts
    return ways


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def band(pts, half=1.5):
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1
        nx, ny = -dy / n * half, dx / n * half
        left.append((x + nx, y + ny)); right.append((x - nx, y - ny))
    return left + right[::-1]


def octagon(cx, cy, h):
    c = h * math.tan(math.radians(22.5))
    return [(cx - c, cy + h), (cx + c, cy + h), (cx + h, cy + c), (cx + h, cy - c), (cx + c, cy - h), (cx - c, cy - h),
            (cx - h, cy - c), (cx - h, cy + c)]


# The building in turned metres (OpenStreetMap way 216184574): the long main block runs up the page with the entrance
# pavilion at its north end facing the lawn, and a wing to the east at the north end.
OCT = (-38.5, 2.0, 7.0)          # the Four Freedoms gallery: centre and half-width; the cupola is over it
OCT_POLY = octagon(*OCT)
SHOWS = {
    'human': 'Norman Rockwell: The Human Touch (Nov 14, 2026 – May 31, 2027)',
    'holiday': 'Many Lights, One Season: A Holiday Celebration (Nov 20, 2026 – Feb 20, 2027)',
    'calvin': 'Exploring Calvin and Hobbes (Nov 14, 2026 – May 31, 2027)',
    'herriman': 'George Herriman, Krazy Kat, and the Path to Calvin and Hobbes (from Nov 14, 2026)',
}

MAIN = [
    ('Entrance Hall', 'space', f'Entrance hall {GUESS}: admissions desk and coat check, under the front porch',
     rect(-44.5, 22.5, -30.2, 35.3), None),
    ('North Gallery', 'gallery', f'Rockwell galleries, north {GUESS}: {SHOWS["human"]}',
     rect(-50.3, 9.0, -30.2, 22.5), 'Rockwell · North'),
    ('Four Freedoms Gallery', 'gallery', 'Four Freedoms Gallery: the octagonal room under the cupola, with Rockwell’s '
     'Four Freedoms (1943) facing one another', OCT_POLY, 'Four Freedoms'),
    ('Terrace Hall', 'corridor', f'Cross hall to the terrace door {GUESS}: the view over the Housatonic valley',
     rect(-31.5, -0.9, -29.4, 4.9), None),
    ('South Gallery', 'gallery', f'Rockwell galleries, south {GUESS}: {SHOWS["human"]} · {SHOWS["holiday"]}',
     [(-50.3, -16.0), (-25.5, -16.0), (-25.5, -7.3), (-29.4, -7.3), (-29.4, -5.0), (-50.3, -5.0)], 'Rockwell · South'),
    ('East Hall', 'corridor', f'East hall {GUESS}: restrooms, elevator and stairs to the Lower Level',
     [(-30.2, 23.6), (-24.1, 23.6), (-24.1, 5.2), (-29.4, 5.2), (-29.4, 9.0), (-30.2, 9.0)], None),
    ('Museum Store', 'space', f'Museum Store {GUESS}', rect(-24.1, 12.15, -14.6, 23.6), None),
]
MAIN_CLOSED = [rect(-50.3, -5.0, -45.5, 9.0), [(-45.5, 9.0), (-41.4, 9.0), (-45.5, 4.9)],
               [(-35.6, 9.0), (-31.5, 9.0), (-31.5, 4.9)], [(-45.5, -5.0), (-41.4, -5.0), (-45.5, -0.9)],
               [(-35.6, -5.0), (-31.5, -5.0), (-31.5, -0.9)], rect(-31.5, 4.9, -29.4, 9.0)]
MAIN_DOORS = [('Entrance Hall', 'North Gallery', (-37.4, 22.5)), ('North Gallery', 'Four Freedoms Gallery', (-38.5, 9.0)),
              ('Four Freedoms Gallery', 'South Gallery', (-38.5, -5.0)),
              ('Four Freedoms Gallery', 'Terrace Hall', (-31.5, 2.0)), ('North Gallery', 'East Hall', (-30.2, 16.0)),
              ('East Hall', 'Museum Store', (-24.1, 18.0)), ('Entrance Hall', 'East Hall', (-30.2, 23.0))]
MAIN_AMEN = [('entrance', -37.4, 35.3), ('info', -40.5, 30.5), ('coat', -34.0, 30.5), ('shop', -19.3, 18.0),
             ('restroom', -27.0, 19.5), ('elevator', -27.0, 12.0), ('stairs', -27.0, 7.0), ('entrance', -29.4, 2.0)]
MAIN_LABELS = [('Front door: facing the lawn, from the drive and the parking', -37.4, 39.0),
               ('Terrace door ›', -24.0, 2.0),
               ('Approximate: the museum’s own floor plan could not be read', -38.0, -20.0)]

LOWER = [
    ('Lower North Gallery', 'gallery', f'Lower Level gallery, north {GUESS}: {SHOWS["calvin"]}',
     rect(-50.3, 9.0, -30.2, 22.5), 'Lower · North'),
    ('Lower Center Gallery', 'gallery', f'Lower Level gallery, centre {GUESS}: {SHOWS["calvin"]}',
     rect(-50.3, -5.0, -29.4, 9.0), 'Lower · Centre'),
    ('Lower South Gallery', 'gallery', f'Lower Level gallery, south {GUESS}: {SHOWS["herriman"]}',
     [(-50.3, -16.0), (-25.5, -16.0), (-25.5, -7.3), (-29.4, -7.3), (-29.4, -5.0), (-50.3, -5.0)], 'Lower · South'),
    ('Lower East Hall', 'corridor', f'Lower Level hall {GUESS}: stairs, elevator and restrooms',
     [(-30.2, 23.6), (-24.1, 23.6), (-24.1, 5.2), (-29.4, 5.2), (-29.4, 9.0), (-30.2, 9.0)], None),
]
LOWER_CLOSED = [rect(-24.1, 12.15, -14.6, 23.6)]
LOWER_DOORS = [('Lower North Gallery', 'Lower Center Gallery', (-40.0, 9.0)),
               ('Lower Center Gallery', 'Lower South Gallery', (-40.0, -5.0)),
               ('Lower North Gallery', 'Lower East Hall', (-30.2, 16.0))]
LOWER_AMEN = [('restroom', -27.0, 19.5), ('elevator', -27.0, 12.0), ('stairs', -27.0, 7.0)]
LOWER_LABELS = [('Approximate: how the Lower Level is divided is our guess', -38.0, -20.0),
                ('Under the entrance hall and the Museum Store: not open to visitors', -24.0, 30.0)]


def build_grounds(ways):
    museum = ways['216184574'][:-1]
    rooms = [
        ('Lawn', 'corridor', 'The lawn in front of the museum (“like a New England town green”)',
         [(-62.0, 35.3), (40.0, 35.3), (40.0, 97.0), (-62.0, 97.0)], None),
        ('Museum', 'space', 'Norman Rockwell Museum (1993, Robert A. M. Stern): see the Main Level and Lower Level',
         museum, None),
        ('Terrace', 'space', 'Terrace with the Terrace Café (summer) and the view down to the Housatonic River',
         [(-29.4, -7.3), (-25.5, -7.3), (-25.5, -12.0), (-14.0, -12.0), (-14.0, 5.2), (-29.4, 5.2)], None),
        ('Studio Walk', 'corridor', 'Walk to Rockwell’s Studio, under the pergola', band(ways['377980637'], 1.5), None),
        ('Linwood Walk', 'corridor', 'Walk past Linwood House', band(ways['377980855'], 1.2), None),
        ('Rockwell’s Studio', 'gallery', 'Norman Rockwell’s Studio: moved here from Stockbridge’s Main Street in '
         '1986, set up as he left it (open May to early November; closed after Nov 8, 2026)',
         ways['216184517'][:-1], 'Studio'),
        ('Linwood House', 'space', 'Linwood House (1859): museum offices, not open to visitors',
         ways['216184547'][:-1], None),
        ('Drive', 'corridor', 'Drive to the front door (drop-off)', band(ways['377980395'], 2.5), None),
        ('Parking', 'space', 'Main parking lot', ways['377981545'][:-1], None),
        ('South Parking', 'space', 'Parking', ways['940563368'][:-1], None),
        ('South Parking 2', 'space', 'Parking', ways['940563369'][:-1], None),
    ]
    doors = [('Lawn', 'Museum', (-37.4, 35.3)), ('Museum', 'Terrace', (-29.4, 2.0)),
             ('Lawn', 'Studio Walk', (-14.2, 34.3)), ('Studio Walk', 'Rockwell’s Studio', (88.0, 80.0)),
             ('Lawn', 'Linwood Walk', (-20.4, 65.1)), ('Linwood Walk', 'Linwood House', (17.0, 100.0)),
             ('Lawn', 'Drive', (-41.4, 50.9)), ('Studio Walk', 'Terrace', (-14.0, 4.0))]
    amen = [('entrance', -37.4, 35.3), ('dining', -21.0, -4.0), ('entrance', 86.0, 87.0)]
    labels = [('P · Free parking', -160.0, 100.0), ('P', -35.5, -34.5), ('P', 2.0, -58.0),
              ('GLENDALE ROAD (Route 183) ›', -40.0, -78.0),
              ('Housatonic River (down the hill) ›', 60.0, -30.0),
              ('Studio closes for the season after Nov 8, 2026', 70.0, 98.0),
              ('Terrace Café: summer only', -10.0, -16.0)]
    rr = []
    for rid, kind, name, poly, short in rooms:
        r = {'id': rid, 'kind': kind, 'name': name, 'poly': [G(*q) for q in poly]}
        if kind == 'gallery': r['label'] = short
        rr.append(r)
    return {'id': 'G', 'label': 'Grounds & Studio', 'order': 0, 'transform': [1, 0, 0],
            'area': 'Parking · the lawn · front door · Terrace and Terrace Café · Rockwell’s Studio · Linwood House',
            'rooms': rr, 'closed': [],
            'amenities': [{'type': t, 'at': G(x, y)} for t, x, y in amen],
            'labels': [{'text': t, 'kind': 'area', 'at': G(x, y)} for t, x, y in labels],
            'doors': [{'a': a, 'b': b, 'at': G(*p), 'width': 10, 'axis': 'o'} for a, b, p in doors],
            'homeView': ['Museum', 'Rockwell’s Studio']}


def building_floor(fid, label, order, area, rooms, closed, doors, amen, labels):
    rr = []
    for rid, kind, name, poly, short in rooms:
        r = {'id': rid, 'kind': kind, 'name': name, 'poly': [B(*q) for q in poly]}
        if kind == 'gallery': r['label'] = short
        rr.append(r)
    # the same frame as the grounds: G = B * KG/KB + (154*KG, 86*KG)
    return {'id': fid, 'label': label, 'order': order, 'transform': [KG / KB, 154 * KG, 86 * KG], 'area': area, 'rooms': rr,
            'closed': [{'poly': [B(*q) for q in c]} for c in closed],
            'amenities': [{'type': t, 'at': B(x, y)} for t, x, y in amen],
            'labels': [{'text': t, 'kind': 'area', 'at': B(x, y)} for t, x, y in labels],
            'doors': [{'a': a, 'b': b, 'at': B(*p), 'width': 16, 'axis': 'o'} for a, b, p in doors]}


def build_floors(ways):
    floors = [build_grounds(ways),
              building_floor('LL', 'Lower Level', 1, 'Exhibitions: Exploring Calvin and Hobbes · George Herriman and '
                             'Krazy Kat (from Nov 14, 2026) · restrooms (approximate)', LOWER, LOWER_CLOSED,
                             LOWER_DOORS, LOWER_AMEN, LOWER_LABELS),
              building_floor('1', 'Main Level', 2, 'Entrance and admissions · Four Freedoms Gallery · Rockwell '
                             'galleries · Museum Store · terrace door (approximate)', MAIN, MAIN_CLOSED, MAIN_DOORS,
                             MAIN_AMEN, MAIN_LABELS)]
    for f in floors:
        ids = {r['id'] for r in f['rooms']}
        for d in f['doors']:
            assert d['a'] in ids and d['b'] in ids, (f['id'], d)
    return {'about': 'Built by tools/build_nrm.py. The grounds and the building’s outline come from OpenStreetMap. '
                     'The rooms inside are approximate: the museum’s website could not be read, so they are drawn '
                     'from descriptions of the building (the octagonal Four Freedoms gallery under the cupola, '
                     'galleries in a line, more galleries one floor down).',
            'source': 'OpenStreetMap (grounds and outlines); Robert A. M. Stern Architects’ and visitors’ descriptions '
                      'of the building; the museum’s exhibition announcements (Oct 2026)',
            'units': f'grounds: metres x {KG}; building: metres x {KB}; turned 17.5 degrees (north is a little to '
                     'the left of up)',
            'approximate': True, 'defaultFloor': '1', 'galleryWord': 'Gallery', 'floors': floors}


# ---- works ------------------------------------------------------------------------------------------------------

def norm(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '', s)


def key_title(t):
    t = re.sub(r'^[\s"“”]+|[\s"“”]+$', '', t or '')
    t = re.sub(r'^(The|A)\s+|,\s*The$', '', t.split('(')[0].strip())
    return norm(t)


def year_of(date):
    m = re.search(r'(\d{4})', date or '')
    return int(m[1]) if m else None


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
    return f'data/nrm/images/{key}.jpg'


def wikidata():
    q = '''SELECT ?w ?title ?creator ?date ?img ?acc ?material ?type WHERE {
      ?w wdt:P195 wd:%s . OPTIONAL { ?w rdfs:label ?title FILTER(lang(?title)="en") }
      OPTIONAL { ?w wdt:P170 ?c . ?c rdfs:label ?creator FILTER(lang(?creator)="en") }
      OPTIONAL { ?w wdt:P571 ?date } OPTIONAL { ?w wdt:P18 ?img }
      OPTIONAL { ?w wdt:P31 ?t . ?t rdfs:label ?type FILTER(lang(?type)="en") }
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
        r = rows.setdefault(qid, {'qid': qid, 'title': v.get('title') or '', 'artist': set(), 'date': '',
                                  'image': None, 'accession': '', 'medium': set(), 'type': ''})
        if v.get('creator'): r['artist'].add(v['creator'])
        if v.get('material'): r['medium'].add(v['material'])
        if v.get('date') and not v['date'].startswith('-'): r['date'] = v['date'][:4]
        if v.get('img'): r['image'] = v['img']
        if v.get('acc'): r['accession'] = v['acc']
        if v.get('type'): r['type'] = r['type'] or v['type']
    out = []
    for r in rows.values():
        if not r['title'] or re.fullmatch(r'Q\d+', r['title']): continue
        r['artist'] = ', '.join(sorted(r['artist'])) or 'Unknown artist'
        r['medium'] = ', '.join(sorted(r['medium']))
        out.append(r)
    return out


ART = re.compile(r'^(oil|charcoal|ink|pencil|graphite|watercolou?r|gouache|tempera|acrylic)', re.I)
FREEDOMS = {'freedomofspeech', 'freedomofworship', 'freedomfromwant', 'freedomfromfear', 'fourfreedoms'}
FREEDOMS_NOTE = ('The museum shows the Four Freedoms in the octagonal gallery at the heart of the building. They '
                 'sometimes travel to other museums.')
ROCKWELL_NOTE = ('The museum hangs its Rockwells in the main-floor galleries and changes them; the gallery is our '
                 'guess from the date, and this work may be in storage.')


def gac_rows():
    f = CACHE / 'gac-works.json'
    if not f.exists(): raise SystemExit('run tools/harvest_nrm.py first')
    rows, seen = [], set()
    for w in json.loads(f.read_text()):
        gid = w['gac'].rsplit('/', 1)[1]
        if gid in seen or w['medium'].startswith('Video') or w['type'] == 'Video': continue
        seen.add(gid)
        w['gid'] = gid
        if re.fullmatch(r'\s*["“][^"“”]*["”]\s*', w['title']):              # '"The Right to Know"' -> 'The Right to Know'
            w['title'] = re.sub(r'^[\s"“”]+|[\s"“”]+$', '', w['title'])
        if w['title'] == 'Catch, The': w['title'] = 'The Catch'
        artist = w['artist']
        if 'Rockwell' in w['credit'] and (not artist or artist.startswith('Norman Rockwell')):
            artist = 'Norman Rockwell'
        if artist.startswith('Louis Lamone'): artist = 'Louie Lamone'
        w['artist'] = re.sub(r'\s*\(\d{4}-\d{4}\)', '', artist) or 'Unknown'
        rows.append(w)
    return rows


def build_works(floors):
    rooms = {r['id']: (f['id'], r['name']) for f in floors['floors'] for r in f['rooms']}
    works, archive, seen = [], [], set()

    def add(a, room, note, guessed):
        fl, gname = rooms[room]
        a.update({'gallery': room, 'galleryName': gname, 'floor': fl, 'placeNote': note})
        if guessed: a['placeGuessed'] = True
        works.append({k: v for k, v in a.items() if v not in (None, '')})

    def room_for(title, year):
        if key_title(title) in FREEDOMS or 'fourfreedoms' in norm(title): return 'Four Freedoms Gallery', FREEDOMS_NOTE, False
        if 'fourfreedoms' in norm(title): return 'Four Freedoms Gallery', FREEDOMS_NOTE, True
        return ('North Gallery' if (year or 1950) < 1935 else 'South Gallery'), ROCKWELL_NOTE, True

    for w in gac_rows():
        key = 'nrm-gac-' + w['gid']
        is_art = w['artist'] == 'Norman Rockwell' and (w['type'] in ('Painting', 'Drawing') or ART.match(w['medium']))
        a = {'id': key, 'title': w['title'], 'artist': w['artist'], 'date': w['date'], 'year': year_of(w['date']),
             'medium': w['medium'] or None, 'dimensions': w['dimensions'] or None, 'creditLine': w['credit'] or None,
             'description': (w['text'] or '')[:1500] or None, 'url': w['gac'],
             'image': picture(key, w['image'] and w['image'] + '=w1000'),
             'imageCredit': 'Norman Rockwell Museum, via Google Arts & Culture'}
        if is_art:
            room, note, guessed = room_for(w['title'], a['year'])
            add(a, room, note, guessed)
            seen.add(key_title(w['title']))
        else:
            archive.append(a)
    for w in wikidata():
        if key_title(w['title']) in seen: continue
        seen.add(key_title(w['title']))
        img = None
        if w['image']:
            img = 'https://commons.wikimedia.org/wiki/Special:FilePath/' + \
                  urllib.parse.quote(urllib.parse.unquote(w['image'].rsplit('/', 1)[1])) + '?width=800'
        a = {'id': 'nrm-' + w['qid'], 'title': w['title'], 'artist': w['artist'], 'date': w['date'],
             'year': year_of(w['date']), 'medium': w['medium'] or None, 'accession': w['accession'] or None,
             'url': f'https://www.wikidata.org/wiki/{w["qid"]}', 'wikidata': w['qid'], 'image': img,
             'imageCredit': 'Wikimedia Commons' if img else None}
        if w['artist'] == 'Norman Rockwell':
            room, note, guessed = room_for(w['title'], a['year'])
            add(a, room, note, guessed)
        else:
            archive.append({k: v for k, v in a.items() if v not in (None, '')})
    order = {r['id']: i for f in floors['floors'] for i, r in enumerate(f['rooms'])}
    forder = {f['id']: f['order'] for f in floors['floors']}
    works.sort(key=lambda a: (-forder[a['floor']], order[a['gallery']], a.get('year') or 0))
    return ({'source': 'Norman Rockwell Museum on Google Arts & Culture and Wikidata (CC0); galleries approximate',
             'checked': time.strftime('%Y-%m-%d'), 'count': len(works), 'complete': False, 'artworks': works},
            archive)


def build_guide(works, archive):
    rows = []
    for a in works['artworks']:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a['artist'], 'date': a.get('date'),
                     'year': a.get('year'), 'medium': a.get('medium'), 'accession': a.get('accession'),
                     'url': a['url'], 'imageUrl': a.get('image'), 'onView': a['gallery'] == 'Four Freedoms Gallery',
                     'gallery': a['gallery'], 'floor': a['floor']}.items() if v not in (None, '')})
    for a in archive:
        rows.append({k: v for k, v in {'id': a['id'], 'title': a['title'], 'artist': a['artist'], 'date': a.get('date'),
                     'year': a.get('year'), 'medium': a.get('medium'), 'url': a['url'], 'imageUrl': a.get('image'),
                     'onView': False}.items() if v not in (None, '')})
    rows.sort(key=lambda w: (not w['onView'], w['artist'] != 'Norman Rockwell', w.get('year') or 0))
    return {'museum': MUSEUM, 'name': NAME, 'checked': time.strftime('%Y-%m-%d'),
            'source': 'Norman Rockwell Museum on Google Arts & Culture, and Wikidata', 'onViewKnown': False,
            'note': 'The museum owns 574 original works by Norman Rockwell, the largest collection anywhere, and an '
                    'archive of more than 100,000 photographs, letters and papers. This list is what it shows on '
                    'Google Arts & Culture and what Wikidata knows; only the Four Freedoms have a known gallery.',
            'works': rows}


def main():
    OUT.mkdir(exist_ok=True)
    floors = build_floors(osm())
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    works, archive = build_works(floors)
    (OUT / 'artworks.json').write_text(json.dumps(works, ensure_ascii=False, separators=(',', ':')))
    guide = build_guide(works, archive)
    (ROOT / 'data' / 'guides' / f'{MUSEUM}.json').write_text(json.dumps(guide, ensure_ascii=False, separators=(',', ':')))
    idx_path = ROOT / 'data' / 'guides.json'
    idx = json.loads(idx_path.read_text())
    idx['museums'][MUSEUM] = {'works': len(guide['works']), 'pictures': sum(bool(w.get('imageUrl')) for w in guide['works']),
                              'onView': sum(w['onView'] for w in guide['works']), 'galleries': True,
                              'checked': guide['checked'], 'source': guide['source']}
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    by = {}
    for a in works['artworks']: by[a['gallery']] = by.get(a['gallery'], 0) + 1
    print(f'{works["count"]} works on the map ({sum("image" in a for a in works["artworks"])} with pictures), '
          f'{len(archive)} archive items and other artists for the museum page')
    for k, v in by.items(): print(f'  {k}: {v}')


if __name__ == '__main__':
    sys.exit(main())
