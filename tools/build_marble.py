#!/usr/bin/env python3
"""Build the Marble House (Newport, RI) map guide (run: python3 tools/harvest_marble.py, then this).

    data/marble/floors.json         the grounds, the basement and the two floors on the tour, seen from above (flat 2D)
    data/marble/artworks.json       the house's objects, each in its room
    data/marble/images/             their pictures, made smaller for phones
    data/guides/Q2650982.json       the same objects, for the museum page

Where the information comes from
--------------------------------
The map
  - Grounds (floor G): OpenStreetMap (www.openstreetmap.org/api/0.6/map, cached in .cache/marble/osm.xml): the house
    (way 371945268), the grounds (1225569818), the Chinese Tea House (1285803583), the visitor parking across Bellevue
    Avenue (371945261), the avenue (19360222) and the Cliff Walk (629887171 + 432062187). Metres east/north of the
    house (41.461956 N, 71.305617 W). The Society's accessibility page gives the distances and where the restrooms are.
  - House floors 1 and 2: traced from Richard Morris Hunt's own office copies of the plans, "Proposed villa for W. K.
    Vanderbilt Esq., Newport R.I.", No. 3 First Story Plan (stamped Jan 14 1889; Library of Congress, Prints &
    Photographs, LCCN 2024633241) and No. 4 Second Story Plan (LCCN 2017648779). Drawn as on the plans: the ocean
    (east) side at the top, the portico on Bellevue Avenue at the bottom. Units: pixels of the 1024-pixel copies the
    Library serves. The house was built from these plans (1888-1892) and the rooms match the 1971 National Register
    description, but the plans name rooms as they were planned in 1889: the plan's Grand Salon is the Gold Room
    (ballroom), its Library the Gothic Room and its Morning Room today's Library. Which bedroom is shown as whose today
    is our reading of the plan's names (Mrs. V., Mr. V., Miss V. = Consuelo); the map says so.
  - Basement (floor B): no plan of the basement as built is published. The Society says the Museum Store and the
    restrooms are down there, reached by stairs (or the staff-run elevator) at the end of the tour, and 15 steps lead
    from the store up to the path out. Only the house outline is drawn; the places inside it are our guess.

The objects
  The Preservation Society's Digital Collections (see tools/harvest_marble.py): objects that name Marble House, or
  came from its owners, Alva Vanderbilt (Belmont) and Frederick H. Prince, whose estate sold the house with its
  furniture to the Society in 1963. Rooms come from each record's own text; objects whose room no source gives are
  listed on the museum page but not put on the map.
"""
import html
import io
import json
import math
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'marble'
CACHE = ROOT / '.cache' / 'marble'
MUSEUM = 'Q2650982'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
COLL = 'https://newportmansions.rediscoverysoftware.com/'
APPROX = 'Approximate'

# ---- grounds (floor G) ----------------------------------------------------------------------------------------------

LAT0, LON0 = 41.461956, -71.305617
K = 2.4                     # map units per metre on the grounds


def G(x, y):
    """Metres east/north of the house -> map units (north up)."""
    return [round((x + 210) * K, 1), round((120 - y) * K, 1)]


def osm():
    f = CACHE / 'osm.xml'
    if not f.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        url = 'https://www.openstreetmap.org/api/0.6/map?bbox=-71.3090,41.4595,-71.3010,41.4645'
        out = subprocess.run(['curl', '-s', '-f', '-m', '90', '-A', UA, url], capture_output=True).stdout
        if not out: raise SystemExit('OpenStreetMap did not answer')
        f.write_bytes(out)
    root = ET.parse(f).getroot()
    nodes = {n.get('id'): (float(n.get('lat')), float(n.get('lon'))) for n in root.iter('node')}
    ways = {}
    for w in root.iter('way'):
        pts = []
        for nd in w.findall('nd'):
            if nd.get('ref') not in nodes: continue
            lat, lon = nodes[nd.get('ref')]
            pts.append(((lon - LON0) * 111320 * math.cos(math.radians(LAT0)), (lat - LAT0) * 110540))
        ways[w.get('id')] = pts
    return ways


def band(pts, half=3.0):
    """A path drawn as a band `half` metres either side of its line."""
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1
        nx, ny = -dy / n * half, dx / n * half
        left.append((x + nx, y + ny)); right.append((x - nx, y - ny))
    return left + right[::-1]


def inside(pts, y0=-75, y1=120):
    return [p for p in pts if y0 <= p[1] <= y1]


def grounds(ways):
    cliff = inside(ways['629887171'], -75, 120) + inside(ways['432062187'], -75, 120)
    rooms = [
        ('Grounds', 'space', 'Marble House grounds: the front lawn, the circular drive and the back lawn to the sea',
         ways['1225569818'][:-1]),
        ('Marble House', 'space', 'Marble House (1892): the house tour. Pick floor 1, 2 or B above to see the rooms',
         ways['371945268'][:-1]),
        ('Chinese Tea House', 'space', 'Chinese Tea House (1914): Afternoon Tea & Dining (book ahead) and restrooms '
                                       'inside; 10 steps up, not accessible', ways['1285803583'][:-1]),
        ('Parking', 'space', 'Visitor parking (free, 3 accessible spaces), across Bellevue Avenue: about 150 m '
                             '(503 ft) to the front door', ways['371945261'][:-1]),
        ('Bellevue Avenue', 'corridor', 'Bellevue Avenue: the main gates', band(inside(ways['19360222']), 5)),
        ('Cliff Walk', 'corridor', 'Cliff Walk: the public path along the ocean, below the Tea House', band(cliff, 2.5)),
    ]
    doors = [('Parking', 'Bellevue Avenue', (-99, 75)), ('Bellevue Avenue', 'Grounds', (-77, 8)),
             ('Grounds', 'Marble House', (-16, 12)), ('Grounds', 'Chinese Tea House', (142, 3)),
             ('Grounds', 'Cliff Walk', (138, 37))]
    amen = [('entrance', -77, 8), ('entrance', -18, 12), ('info', -9, 12), ('shop', -4, 28), ('restroom', 8, 0),
            ('dining', 147, 3), ('restroom', 154, 3)]
    labels = [('P · Parking (free)', 'area', -150, 108), ('Main gates', 'area', -62, -10),
              ('Front door: tickets inside the hall', 'area', -40, -20), ('Back lawn', 'area', 70, 40),
              ('Chinese Tea House', 'area', 150, -18), ('Atlantic Ocean', 'area', 190, -50),
              ('Museum Store and restrooms: in the basement, at the end of the tour', 'area', 20, 55),
              ('House to Tea House: about 250 m (820 ft)', 'area', 70, -30)]
    return rooms, [], doors, amen, labels


# ---- the house (floors 1, 2 and B) -----------------------------------------------------------------------------------
# Units: pixels of Hunt's plans as served by the Library of Congress (1024 px wide); the top is the ocean (east) side.

def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


TB = 'Hunt’s 1889 plan'
HOUSE_1 = [
    ('Main Hall', 'gallery', 'Main Hall: yellow Siena marble, the grand staircase and, on the landing, Karl Bitter’s '
                             'reliefs of Hunt and Mansart',
     [(330, 385), (705, 385), (705, 465), (610, 465), (610, 745), (420, 745), (420, 465), (330, 465)], 'Main Hall'),
    ('Dining Room', 'gallery', 'Dining Room: pink Numidian marble, gilt-bronze chairs and a ceiling painting',
     rect(135, 470, 415, 665), 'Dining Room'),
    ('Gold Room', 'gallery', 'Gold Room: the ballroom, gilded carving, mirrors and bronze chandeliers by Allard '
                             '(the plan calls it the Grand Salon)', rect(615, 470, 905, 665), 'Gold Room'),
    ('Gothic Room', 'gallery', 'Gothic Room: carved oak and stained glass, built for Alva’s medieval collection '
                               '(the plan calls it the Library)', rect(715, 190, 905, 465), 'Gothic Room'),
    ('Library', 'gallery', 'Library: walnut panels in the Louis XV style (the plan calls it the Morning Room)',
     rect(135, 190, 325, 300), 'Library'),
    ('Butler’s Pantry', 'gallery', 'Butler’s Pantry and the service stairs',
     [(245, 300), (325, 300), (325, 465), (135, 465), (135, 370), (245, 370)], 'Pantry'),
    ('Terrace', 'space', 'Back terrace, between the two wings, facing the lawn and the ocean', rect(330, 100, 705, 385),
     None),
    ('Portico', 'space', 'Front portico: the front door, facing Bellevue Avenue', rect(410, 745, 625, 880), None),
]
HOUSE_1_CLOSED = [rect(135, 300, 245, 370)]                                   # the back stairs
HOUSE_1_DOORS = [('Portico', 'Main Hall', (515, 745)), ('Main Hall', 'Dining Room', (420, 560)),
                 ('Main Hall', 'Gold Room', (612, 560)), ('Main Hall', 'Gothic Room', (708, 425)),
                 ('Gothic Room', 'Gold Room', (810, 467)), ('Main Hall', 'Terrace', (515, 385)),
                 ('Main Hall', 'Butler’s Pantry', (328, 425)), ('Butler’s Pantry', 'Dining Room', (230, 467)),
                 ('Butler’s Pantry', 'Library', (285, 300)), ('Library', 'Terrace', (327, 250))]
HOUSE_1_AMENITIES = [('entrance', 515, 830), ('stairs', 460, 525), ('stairs', 190, 335)]
HOUSE_1_LABELS = [('Ramp to the front door; elevator run by staff (ask a guide)', 'area', 515, 905),
                  ('Mezzanine: 20 steps up the grand stair, family sitting rooms (no elevator)', 'area', 520, 420),
                  ('Restrooms and the Museum Store: in the basement, at the end of the tour', 'area', 760, 760),
                  ('↑ East: the back lawn and the ocean', 'area', 520, 20)]

# Floor 2: the second-story sheet is drawn at another size; F2 puts it over floor 1 (outer walls and front matched).
HOUSE_2 = [
    ('Upper Hall', 'corridor', 'Upper hall and the top of the grand staircase',
     [(370, 290), (615, 290), (615, 385), (725, 385), (725, 545), (370, 545), (370, 425), (80, 425), (80, 385),
      (370, 385)], None),
    ('Mrs. Vanderbilt’s Bedroom', 'gallery', 'Mrs. Vanderbilt’s Bedroom: Alva’s room, the largest bedroom (the plan’s '
                                             '“Mrs. V’s Room”)', rect(725, 385, 935, 598), 'Mrs. Vanderbilt'),
    ('Consuelo’s Bedroom', 'gallery', 'Consuelo Vanderbilt’s Bedroom: the only daughter, married to the Duke of '
                                      'Marlborough in 1895 (the plan’s “Miss V’s Room”)', rect(165, 425, 365, 598),
     'Consuelo'),
    ('Mr. Vanderbilt’s Bedroom', 'gallery', 'Mr. Vanderbilt’s Bedroom: William K. Vanderbilt, over the front portico '
                                            '(the plan’s “Mr. V’s Room”)', rect(455, 545, 600, 680), 'Mr. Vanderbilt'),
    ('Sons’ Bedroom', 'gallery', 'Bedroom of the Vanderbilt sons, William Jr. and Harold (the plan’s “Master V.”)',
     rect(765, 250, 935, 385), 'Bedroom'),
    ('South Wing Bedroom', 'gallery', 'Bedroom in the south wing, over the Gothic Room', rect(710, 68, 935, 200),
     'Bedroom'),
    ('North Wing Bedrooms', 'gallery', 'Schoolroom and bedrooms in the north wing, over the Library',
     [(80, 75), (290, 75), (290, 385), (200, 385), (200, 195), (80, 195)], 'Bedrooms'),
    ('Guest Bedroom', 'gallery', 'Small bedroom off the upper hall', rect(615, 290, 700, 385), 'Bedroom'),
]
HOUSE_2_CLOSED = [rect(80, 195, 200, 385), rect(290, 290, 370, 385),       # back stairs, maid, bath; dressing room
                  rect(80, 425, 165, 598), rect(365, 545, 455, 680),       # Consuelo's dressing room; baths
                  rect(600, 545, 725, 598), rect(700, 200, 935, 250), rect(700, 250, 765, 385)]
HOUSE_2_DOORS = [('Upper Hall', 'Mrs. Vanderbilt’s Bedroom', (725, 470)), ('Upper Hall', 'Consuelo’s Bedroom',
                                                                            (300, 425)),
                 ('Upper Hall', 'Mr. Vanderbilt’s Bedroom', (530, 545)), ('Upper Hall', 'Guest Bedroom', (660, 385)),
                 ('Upper Hall', 'North Wing Bedrooms', (245, 385)), ('Mrs. Vanderbilt’s Bedroom', 'Sons’ Bedroom', (850, 385)),
                 ('Sons’ Bedroom', 'South Wing Bedroom', (850, 210))]
HOUSE_2_AMENITIES = [('stairs', 575, 450), ('stairs', 140, 240)]
HOUSE_2_LABELS = [(APPROX + ': room uses from ' + TB + '; today’s rooms may be arranged differently', 'area', 500, 760),
                  ('One accessible restroom on this floor: a guide will take you', 'area', 500, 800),
                  ('Third floor: not open', 'area', 500, 200)]

F1_OUTLINE = [(125, 180), (330, 180), (330, 385), (705, 385), (705, 180), (912, 180), (912, 670), (625, 670),
              (625, 745), (410, 745), (410, 670), (125, 670)]
HOUSE_B = [
    ('Basement', 'space', 'Basement: service rooms; the Museum Store and restrooms (places approximate)', F1_OUTLINE,
     None),
    ('Museum Store', 'space', 'The Museum Store (place approximate): 15 steps up from here to the path out',
     rect(150, 470, 400, 650), None),
]
HOUSE_B_DOORS = [('Basement', 'Museum Store', (275, 470))]
HOUSE_B_AMENITIES = [('stairs', 460, 525), ('shop', 275, 560), ('restroom', 760, 560), ('entrance', 135, 620)]
HOUSE_B_LABELS = [(APPROX + ': no plan of the basement as built is published', 'area', 520, 820),
                  ('Exit: 15 steps up to the path (place approximate)', 'area', 135, 720)]

S = 0.6                 # map units per pixel of the plans
KX2, KY2 = (912 - 125) / (935 - 70), (670 - 180) / (598 - 68)


def build_floors(ways):
    g_rooms, g_closed, g_doors, g_amen, g_labels = grounds(ways)
    f1 = lambda x, y: [round(x * S, 1), round(y * S, 1)]
    f2 = lambda x, y: f1(125 + (x - 70) * KX2, 180 + (y - 68) * KY2)
    # put the house floors over the house on the grounds map, so switching floors keeps the house in view
    hx = sum(p[0] for p in ways['371945268'][:-1]) / 12
    hy = sum(p[1] for p in ways['371945268'][:-1]) / 12
    cx, cy = f1(518, 430)
    gx, gy = G(hx, hy)
    shift = (round(gx - cx, 1), round(gy - cy, 1))
    spec = [
        ('G', 'Grounds & Tea House', 'Parking · grounds · Chinese Tea House (tea, restrooms) · Cliff Walk', 0, G,
         [(a, b, c, d, None) for a, b, c, d in g_rooms], g_closed, g_doors, g_amen, g_labels),
        ('B', 'House · Basement', 'Museum Store · restrooms (places approximate)', 1, f1, HOUSE_B, [], HOUSE_B_DOORS,
         HOUSE_B_AMENITIES, HOUSE_B_LABELS),
        ('1', 'House · Floor 1', 'Main Hall · Gold Room · Gothic Room · Dining Room · Library', 2, f1, HOUSE_1,
         HOUSE_1_CLOSED, HOUSE_1_DOORS, HOUSE_1_AMENITIES, HOUSE_1_LABELS),
        ('2', 'House · Floor 2', 'Mrs. Vanderbilt’s, Consuelo’s and Mr. Vanderbilt’s bedrooms', 3, f2, HOUSE_2,
         HOUSE_2_CLOSED, HOUSE_2_DOORS, HOUSE_2_AMENITIES, HOUSE_2_LABELS),
    ]
    floors = []
    for fid, label, area, order, pt, rooms_in, closed_in, doors_in, amen, labels in spec:
        rooms = []
        for rid, kind, name, poly, short in rooms_in:
            r = {'id': rid, 'kind': kind, 'name': name, 'poly': [pt(*q) for q in poly]}
            if kind == 'gallery': r['label'] = short or rid
            rooms.append(r)
        ids = {r['id'] for r in rooms}
        doors = [{'a': a, 'b': b, 'at': pt(x, y), 'width': 14, 'axis': 'o'} for a, b, (x, y) in doors_in]
        for d in doors:
            assert d['a'] in ids and d['b'] in ids, (fid, d)
        floors.append({'id': fid, 'label': label, 'area': area, 'order': order,
                       'transform': [1, 0, 0] if fid == 'G' else [1, *shift],
                       'rooms': rooms, 'closed': [{'poly': [pt(*q) for q in c]} for c in closed_in],
                       'amenities': [{'type': t, 'at': pt(x, y)} for t, x, y in amen],
                       'labels': [{'text': t, 'kind': k, 'at': pt(x, y)} for t, k, x, y in labels],
                       'doors': doors, **({'homeView': ['Marble House', 'Parking', 'Chinese Tea House']}
                                          if fid == 'G' else {})})
    return {'about': 'Built by tools/build_marble.py. The grounds come from OpenStreetMap; floors 1 and 2 are traced '
                     'from Richard Morris Hunt’s 1889 plans of the house (Library of Congress). The rooms on floor 2 '
                     'are named from the plan, so which bedroom is whose is approximate. The basement has no '
                     'published plan: only its outline is drawn, and the places in it are approximate.',
            'source': 'OpenStreetMap (grounds), Richard Morris Hunt’s first- and second-story plans, 1889 (Library of '
                      'Congress), the Preservation Society of Newport County’s accessibility page (visitor facilities)',
            'units': f'grounds: metres x {K}, north up; house: pixels of the plans x {S} (the ocean side at the top)',
            'defaultFloor': '1', 'galleryWord': 'Room', 'floors': floors}


# ---- objects -------------------------------------------------------------------------------------------------------

REC = 'its record in the Preservation Society’s collection'
# catalog number -> (room, how we know, guessed); filled in from the records (see the harvest's objects.json)
GUESS = ' (our guess: the Society doesn’t say which room it is in today)'
PLACES = {
    'PSNC.10545': ('Gold Room', f'Installed on the Gold Room (ballroom) ceiling ({REC}).', False),
    'PSNC.12603': ('Gothic Room', f'Kept in the Gothic Room by Alva Vanderbilt and by Frederick H. Prince ({REC}); '
                                  'bought back for the house in 2014' + GUESS + '.', True),
    'PSNC.526': ('Gothic Room', 'A Gothic tapestry from Alva Belmont’s collection of medieval art' + GUESS + '.', True),
    'PSNC.230': ('Gothic Room', 'Gothic-style furniture from the house' + GUESS + '.', True),
    'PSNC.231': ('Gothic Room', 'Gothic-style table by Allard, who made the Gothic Room' + GUESS + '.', True),
    'PSNC.11350': ('Gothic Room', 'Gothic-window bookends from Frederick H. Prince’s house' + GUESS + '.', True),
    'PSNC.415': ('Library', 'Louis XV-style walnut by Allard, like the Library’s walnut panels' + GUESS + '.', True),
    'PSNC.491': ('Library', 'Louis XV-style walnut by Allard, like the Library’s walnut panels' + GUESS + '.', True),
    'PSNC.89': ('Library', 'Carved walnut and cane, like the Library’s Louis XV-style walnut' + GUESS + '.', True),
    'PSNC.85': ('Library', 'A walnut desk cabinet from the house' + GUESS + '.', True),
}
NOT_MARBLE = re.compile(r'Cornelius Vanderbilt|Palazzo|Road Coach|Napkin|Sleigh|Carriage|Brougham|Omnibus', re.I)
SKIP = {'PSNC.10462', 'PSNC.6255', 'PSNC.4426'}          # records that the searches catch but that never belonged to Marble House

def clean(s):
    s = html.unescape(re.sub(r'<br\s*/?>', '\n', s or ''))
    return re.sub(r'[ \t]+', ' ', re.sub(r'<[^>]+>', '', s)).strip()


def artists(s):
    names = []
    for part in (s or '').split('||'):
        name, _, role = part.partition('__')
        name = name.strip()
        if not name or name.lower().startswith('undetermined'): continue
        if ',' in name and not re.search(r'&|Inc|Co\.|Fils|Studios', name):
            last, first = [x.strip() for x in name.split(',', 1)]
            name = f'{first} {last}'
        role = role.strip().strip('[]')
        if names and role in ('Manufacturer', 'Retailer'): continue      # the designer is named already
        names.append(name + (f' ({role.lower()})' if role and role not in ('Artist', 'Maker', 'Creator') else ''))
    return ', '.join(names) or 'Unknown maker'


def year_of(date):
    m = re.search(r'(\d{4})', date or '')
    if m: return int(m[1])
    m = re.search(r'(\d+)(?:st|nd|rd|th)[- ]+c', (date or '').lower())
    return (int(m[1]) - 1) * 100 + 50 if m else None


def picture(key, path):
    """Download once (politely) and save a phone-sized JPEG; returns the app path."""
    if not path: return None
    raw = CACHE / 'img' / f'{key}.bin'
    if not raw.exists():
        raw.parent.mkdir(parents=True, exist_ok=True)
        url = COLL + 'FullImages' + path
        out = subprocess.run(['curl', '-s', '-f', '-L', '-m', '90', '-A', UA, url], capture_output=True).stdout
        time.sleep(2)
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
    return f'data/marble/images/{key}.jpg'



def build_works(floors):
    names = {r['id']: (r['name'], f['id']) for f in floors['floors'] for r in f['rooms']}
    objs = json.loads((CACHE / 'objects.json').read_text())
    objs.pop('_words', None)
    works, extra = [], []
    for r in objs.values():
        if 'images' not in r: continue                      # not one of Marble House's objects
        if r['CAT_NBR'] in SKIP or NOT_MARBLE.search(r['FORM'] + ' ' + r.get('CATEG_20', '')): continue
        key = 'marble-' + re.sub(r'[^a-z0-9]+', '-', r['CAT_NBR'].lower()).strip('-')
        img = picture(key, (r['images'] or [None])[0])
        text = clean(r.get('OBJ_MEM'))
        a = {'id': key, 'title': clean(r['FORM']), 'artist': artists(r.get('ARTIST')), 'date': r.get('CATEG_16') or None,
             'year': year_of(r.get('CATEG_16')), 'medium': (r.get('MATERIAL') or '').replace(' --', ',').title() or None,
             'type': (r.get('CAT_NAM') or '').title() or None,
             'dimensions': re.sub(r'\s*__\s*', ' · ', re.sub(r'\[(\w)\]', r'\1 ', r.get('WEIGHT') or '')).strip() or None,
             'description': text[:1500] or None, 'credit': r.get('CREDIT_LINE') or None,
             'accession': r['CAT_NBR'],
             'url': f'{COLL}mDetail.aspx?rID={r["record_id"]}&db=objects&dir=NEWPHIST',
             'image': img, 'imageCredit': 'The Preservation Society of Newport County' if img else None}
        place = PLACES.get(r['CAT_NBR'])
        if not place:
            extra.append({x: y for x, y in a.items() if y not in (None, '')})
            continue
        room, how, guessed = place
        name, floor = names[room]
        a.update({'gallery': room, 'galleryName': name, 'floor': floor, 'placeNote': how})
        if guessed: a['placeGuessed'] = True
        works.append({x: y for x, y in a.items() if y not in (None, '')})
    order = {r['id']: i for f in floors['floors'] for i, r in enumerate(f['rooms'])}
    forder = {f['id']: f['order'] for f in floors['floors']}
    works.sort(key=lambda a: (forder[a['floor']], order[a['gallery']], a.get('year') or 0))
    extra.sort(key=lambda a: a.get('year') or 0)
    return ({'source': 'The Preservation Society of Newport County, Digital Collections; rooms from each record',
             'checked': time.strftime('%Y-%m-%d'), 'count': len(works), 'complete': False, 'artworks': works}, extra)


def build_guide(works, extra):
    rows = []
    for a in works['artworks'] + extra:
        rows.append({k: v for k, v in {
            'id': a['id'], 'title': a['title'], 'artist': a['artist'], 'date': a.get('date'), 'year': a.get('year'),
            'medium': a.get('medium'), 'url': a['url'], 'imageUrl': a.get('image'), 'onView': 'gallery' in a,
            'gallery': a.get('gallery'), 'floor': a.get('floor')}.items() if v not in (None, '')})
    return {'museum': MUSEUM, 'name': 'Marble House', 'checked': works['checked'],
            'source': 'The Preservation Society of Newport County, Digital Collections', 'onViewKnown': False,
            'note': 'Marble House’s own furniture, paintings and treasures from the Preservation Society’s Digital '
                    'Collections: objects that name the house or came from Alva Vanderbilt Belmont or from Frederick '
                    'H. Prince, who sold the house with its furniture to the Society in 1963. The house holds far more '
                    'than is published online. Objects without a room are in the collection, but the Society doesn’t '
                    'say where they are shown.',
            'works': rows}


def main():
    if not (CACHE / 'objects.json').exists():
        raise SystemExit('run tools/harvest_marble.py first')
    OUT.mkdir(parents=True, exist_ok=True)
    floors = build_floors(osm())
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    works, extra = build_works(floors)
    (OUT / 'artworks.json').write_text(json.dumps(works, ensure_ascii=False, separators=(',', ':')))
    guide = build_guide(works, extra)
    (ROOT / 'data' / 'guides' / f'{MUSEUM}.json').write_text(json.dumps(guide, ensure_ascii=False, separators=(',', ':')))
    idx_path = ROOT / 'data' / 'guides.json'
    idx = json.loads(idx_path.read_text())
    idx['museums'][MUSEUM] = {'works': len(guide['works']), 'pictures': sum(bool(w.get('imageUrl')) for w in guide['works']),
                              'onView': sum(w['onView'] for w in guide['works']), 'galleries': True,
                              'checked': guide['checked'], 'source': guide['source']}
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    by = {}
    for a in works['artworks']: by[a['gallery']] = by.get(a['gallery'], 0) + 1
    print(f'{works["count"]} objects on the map ({sum(bool(a.get("placeGuessed")) for a in works["artworks"])} with a '
          f'guessed room), {len(extra)} more without a room, '
          f'{sum("image" in a for a in works["artworks"] + extra)} pictures')
    for k, v in by.items(): print(f'  {k}: {v}')


if __name__ == '__main__':
    sys.exit(main())
