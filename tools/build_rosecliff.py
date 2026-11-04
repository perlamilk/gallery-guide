#!/usr/bin/env python3
"""Build the Rosecliff (Newport, RI) map guide (run: python3 tools/harvest_rosecliff.py, then this).

    data/rosecliff/floors.json         the grounds and every floor of the house, seen from above (flat 2D, north up)
    data/rosecliff/artworks.json       the house's objects, each in its room
    data/rosecliff/images/             their pictures, made smaller for phones
    data/guides/Q2166814.json          the same objects, for the museum page

Where the information comes from
--------------------------------
The map
  - Grounds (floor G): OpenStreetMap (www.openstreetmap.org/api/0.6/map, cached in .cache/rosecliff/osm.xml): the house
    (way 371945269), the visitor parking next to it (371945263), the drive from Bellevue Avenue (874527389), Bellevue
    Avenue (19360222), the Cliff Walk (629887171) and the garden south of the house (936703164). Metres east/north of
    the house (41.46500 N, 71.30454 W). OpenStreetMap has no boundary for the estate, so the lawn is drawn as a
    rectangle from Bellevue Avenue to the Cliff Walk (approximate). The Society's accessibility page gives the
    parking, the distances, the lift, the elevator and the restrooms.
  - House floors 1 and 2: traced from Stanford White's own plans, "Oelrichs Residence, Newport, R.I., 1902", plate 173
    of "A Monograph of the Work of McKim, Mead & White, 1879-1915" (vol. 2; public domain; Internet Archive
    gri_33125006526137, page n154). Units: pixels of that page at 3000 x 2004, cropped (floor 1 from x 0, floor 2 from
    x 1440, both from y 801). On the plate the terrace and the ocean (east) are at the top and north is on the left;
    we turn them a quarter turn so north is up, like the grounds (checked against the house outline in OpenStreetMap:
    the forecourt opens west, the bay of the heart-shaped staircase sticks out to the south). The plan calls the
    Ballroom the "Living Room".
  - Floor 2 today holds the Society's exhibitions ("Revolution Reimagined: Evolving Stories from Newport's Past" in
    2026). The plan shows the bedrooms; the exhibition uses them as galleries, and the route through them may differ.
  - Basement (floor B): no plan is published. The Society says the Museum Store and the restrooms are down there
    (27 stairs from floor 1; the elevator doesn't go there). Only the outline is drawn; places inside are approximate.

The objects
  The Preservation Society's Digital Collections (see tools/harvest_rosecliff.py): objects that name Rosecliff or came
  from its owners, Theresa Fair Oelrichs (who built it, 1899-1902) and the J. Edgar Monroe family, who gave the house
  and its contents to the Society in 1971. Rooms come from each record's own text; objects whose room no source gives
  are listed on the museum page but not put on the map.
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
OUT = ROOT / 'data' / 'rosecliff'
CACHE = ROOT / '.cache' / 'rosecliff'
MUSEUM = 'Q2166814'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
COLL = 'https://newportmansions.rediscoverysoftware.com/'
APPROX = 'Approximate'

# ---- grounds (floor G) ----------------------------------------------------------------------------------------------

LAT0, LON0 = 41.4650022, -71.3045382
K = 2.4                     # map units per metre on the grounds


def G(x, y):
    """Metres east/north of the house -> map units (north up)."""
    return [round((x + 200) * K, 1), round((125 - y) * K, 1)]


def osm():
    f = CACHE / 'osm.xml'
    if not f.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        url = 'https://www.openstreetmap.org/api/0.6/map?bbox=-71.3085,41.4630,-71.3010,41.4672'
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
    """A street drawn as a band `half` metres either side of its line."""
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1
        nx, ny = -dy / n * half, dx / n * half
        left.append((x + nx, y + ny)); right.append((x - nx, y - ny))
    return left + right[::-1]


def inside(pts, y0=-120, y1=130):
    return [p for p in pts if y0 <= p[1] <= y1]


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def grounds(ways):
    rooms = [
        ('Grounds', 'space', 'Rosecliff grounds: the lawn from Bellevue Avenue to the Cliff Walk, with the rose garden '
                             '(boundary approximate)', rect(-186, -95, 118, 118)),
        ('Rosecliff', 'space', 'Rosecliff (1902): the house tour. Pick floor 1, 2 or B above to see the rooms',
         ways['371945269'][:-1]),
        ('Rose Garden', 'gallery', 'Rose garden south of the house, with gravel paths (outline from OpenStreetMap)',
         ways['936703164'][:-1]),
        ('Parking', 'space', 'Visitor parking (free, 2 accessible spaces), next to the house: about 105 m (345 ft) '
                             'to the front door', ways['371945263'][:-1]),
        ('Drive', 'corridor', 'The drive from the gates on Bellevue Avenue to the house and the parking',
         band(ways['874527389'], 3)),
        ('Bellevue Avenue', 'corridor', 'Bellevue Avenue: the gates; RIPTA bus 67 stops opposite',
         band(inside(ways['19360222']), 5)),
        ('Cliff Walk', 'corridor', 'The Cliff Walk, the public path along the ocean below the lawn',
         band(inside(ways['629887171']), 2)),
    ]
    doors = [('Bellevue Avenue', 'Drive', (-189, -13)), ('Drive', 'Parking', (-34, 60)),
             ('Drive', 'Grounds', (-60, -18)), ('Grounds', 'Rosecliff', (-22, -15)),
             ('Grounds', 'Rose Garden', (-9, -40)), ('Grounds', 'Cliff Walk', (119, 0))]
    amen = [('entrance', -24, -15)]
    labels = [('P · Parking (free)', 'area', -15, 100), ('Gates', 'area', -175, -5),
              ('Front door: 4 steps up, or the lift', 'area', -45, -28),
              ('Restrooms and Museum Store: in the house basement', 'area', -10, 40),
              ('Lawn to the ocean', 'area', 70, 20), ('Bus 67: “Opposite 541 Bellevue”', 'area', -190, 95)]
    return rooms, [], doors, amen, labels


# ---- the house -------------------------------------------------------------------------------------------------------
# Units: pixels of plate 173 (see the top). On the plate the terrace (east) is at the top and north is on the left;
# R() turns it so north is up.

TB = 'Stanford White’s 1902 plans (McKim, Mead & White Monograph, plate 173)'
HOUSE_1 = [
    ('Ballroom', 'gallery', 'Ballroom: the largest in Newport, modelled on the Grand Trianon at Versailles (the plan’s '
                            '“Living Room”); once a roller-skating rink', rect(605, 290, 1110, 548), 'Ballroom'),
    ('Salon', 'gallery', 'Salon', rect(1132, 185, 1362, 460), 'Salon'),
    ('Stair Hall', 'gallery', 'Stair Hall: the famous heart-shaped staircase', rect(1150, 460, 1450, 660),
     'Staircase'),
    ('Vestibule', 'space', 'Front entrance (vestibule): 4 steps up from the forecourt, or the lift',
     rect(1150, 660, 1362, 852), None),
    ('Dining Room', 'gallery', 'Dining Room', rect(385, 590, 600, 850), 'Dining Room'),
    ('Billiard Room', 'gallery', 'Billiard Room', rect(385, 188, 600, 375), 'Billiard Room'),
    ('Hall', 'corridor', 'Service hall: the accessible restroom and the elevator are near here (ask a guide)',
     rect(545, 375, 605, 590), None),
    ('Terrace', 'gallery', 'Terrace on the ocean side, with the steps down to the lawn', rect(600, 75, 1140, 288),
     'Terrace'),
    ('Forecourt', 'gallery', 'Forecourt garden on the Bellevue Avenue side, with its fountain (the plan’s “Garden”)',
     rect(605, 560, 1128, 885), 'Forecourt'),
]
HOUSE_1_CLOSED = [rect(385, 375, 545, 590)]                     # butler's pantry, ante room, service stairs
HOUSE_1_DOORS = [('Vestibule', 'Stair Hall', (1250, 660)), ('Stair Hall', 'Ballroom', (1130, 500)),
                 ('Stair Hall', 'Salon', (1250, 460)), ('Salon', 'Ballroom', (1120, 400)),
                 ('Ballroom', 'Terrace', (860, 290)), ('Ballroom', 'Hall', (605, 470)),
                 ('Hall', 'Billiard Room', (575, 375)), ('Hall', 'Dining Room', (575, 590)),
                 ('Ballroom', 'Forecourt', (860, 548)), ('Forecourt', 'Vestibule', (1140, 800))]
HOUSE_1_AMENITIES = [('entrance', 1250, 870), ('stairs', 1390, 560), ('stairs', 440, 430),
                     ('elevator', 520, 430), ('restroom-all', 445, 390)]
HOUSE_1_LABELS = [('Front door: 4 steps, or the lift', 'area', 1530, 780),
                  ('Restrooms: basement, 27 steps down', 'area', 1600, 600),
                  ('Accessible restroom and staff-run elevator here (places approximate)', 'area', 300, 480),
                  ('West: forecourt, Bellevue Avenue · East: terrace, ocean', 'area', 1680, 480)]


def f2_to_f1(x, y):
    """Floor 2 is drawn on the same plate, 1440 px further right; this puts it over floor 1 (outer walls matched)."""
    return x + 250, 185 + (y - 195) * 665 / 670


EXHIB = 'now a room of the exhibition “Revolution Reimagined: Evolving Stories from Newport’s Past”'
HOUSE_2 = [
    ('Upper Hall', 'gallery', 'Upper hall at the top of the heart-shaped staircase', rect(980, 480, 1200, 690),
     'Upper Hall'),
    ('Corridor', 'corridor', 'Second-floor corridor', rect(300, 490, 980, 575), None),
    ('North-east Bedroom', 'gallery', f'Bedroom (north-east corner, over the Billiard Room), {EXHIB}',
     rect(135, 195, 360, 395), 'Gallery'),
    ('North Bedroom', 'gallery', f'Bedroom (north wing), {EXHIB}', rect(135, 520, 300, 615), 'Gallery'),
    ('North-west Bedroom', 'gallery', f'Bedroom (north-west corner, over the Dining Room), {EXHIB}',
     rect(135, 670, 360, 865), 'Gallery'),
    ('East Bedroom 1', 'gallery', f'Bedroom over the Ballroom, {EXHIB}', rect(360, 300, 480, 450), 'Gallery'),
    ('East Bedroom 2', 'gallery', f'Central bedroom over the Ballroom, {EXHIB}', rect(555, 300, 690, 475),
     'Gallery'),
    ('East Bedroom 3', 'gallery', f'Bedroom over the Ballroom, {EXHIB}', rect(760, 300, 870, 450), 'Gallery'),
    ('South-east Bedroom', 'gallery', f'Bedroom (south-east corner, over the Salon), {EXHIB}',
     rect(880, 195, 1110, 380), 'Gallery'),
    ('South Bedroom', 'gallery', f'Small bedroom off the upper hall, {EXHIB}', rect(890, 575, 980, 680), 'Gallery'),
    ('South-west Bedroom', 'gallery', f'Bedroom (south-west corner, over the entrance), {EXHIB}',
     rect(890, 740, 1110, 865), 'Gallery'),
]
HOUSE_2_CLOSED = [rect(135, 395, 300, 520), rect(135, 615, 300, 670), rect(480, 300, 555, 450),
                  rect(690, 300, 760, 450), rect(880, 380, 980, 490), rect(890, 680, 1100, 740)]
HOUSE_2_DOORS = [('Upper Hall', 'Corridor', (980, 530)), ('Corridor', 'North-east Bedroom', (330, 490)),
                 ('Corridor', 'North Bedroom', (300, 550)), ('Corridor', 'North-west Bedroom', (330, 575)),
                 ('Corridor', 'East Bedroom 1', (420, 490)), ('Corridor', 'East Bedroom 2', (620, 490)),
                 ('Corridor', 'East Bedroom 3', (815, 490)), ('Upper Hall', 'South-east Bedroom', (1040, 480)),
                 ('Upper Hall', 'South Bedroom', (980, 630)), ('Upper Hall', 'South-west Bedroom', (1040, 690))]
HOUSE_2_AMENITIES = [('stairs', 1140, 585), ('stairs', 190, 500), ('elevator', 265, 450)]
HOUSE_2_LABELS = [('38 steps up from floor 1, or the staff-run elevator (place approximate)', 'area', 1300, 480),
                  ('Exhibition floor: rooms from ' + TB + '; the route may differ', 'area', 40, 480)]

F1_OUTLINE = [(385, 185), (605, 185), (605, 290), (1130, 290), (1130, 185), (1362, 185), (1362, 460), (1450, 460),
              (1450, 660), (1362, 660), (1362, 852), (1128, 852), (1128, 560), (605, 560), (605, 852), (385, 852)]
HOUSE_B = [
    ('Basement', 'space', 'Basement: the Museum Store and the restrooms (places approximate)', F1_OUTLINE, None),
]
HOUSE_B_DOORS = []
HOUSE_B_AMENITIES = [('stairs', 1390, 560), ('shop', 860, 420), ('restroom', 470, 700)]
HOUSE_B_LABELS = [('27 steps down from floor 1; the elevator doesn’t come down here', 'area', 1560, 520),
                  (APPROX + ': no plan of the basement is published', 'area', 280, 520)]

S = 0.6                 # map units per pixel of the plans
C = 900                 # turns the plans: R(x, y) = (C - y, x) puts north (the plan's left) at the top


def build_floors(ways):
    g_rooms, g_closed, g_doors, g_amen, g_labels = grounds(ways)
    f1 = lambda x, y: [round((C - y) * S, 1), round(x * S, 1)]
    f2 = lambda x, y: f1(*f2_to_f1(x, y))
    # put the house floors over the house on the grounds map, so switching floors keeps the house in view
    hp = ways['371945269'][:-1]
    hx = sum(p[0] for p in hp) / len(hp)
    hy = sum(p[1] for p in hp) / len(hp)
    cx, cy = f1(915, 520)
    gx, gy = G(hx, hy)
    shift = (round(gx - cx, 1), round(gy - cy, 1))
    spec = [
        ('G', 'Grounds', 'Parking · gates · rose garden · lawn to the Cliff Walk', 0, G,
         [(a, b, c, d, None) for a, b, c, d in g_rooms], g_closed, g_doors, g_amen, g_labels),
        ('B', 'House · Basement', 'Museum Store · restrooms (places approximate)', 1, f1, HOUSE_B, [],
         HOUSE_B_DOORS, HOUSE_B_AMENITIES, HOUSE_B_LABELS),
        ('1', 'House · Floor 1', 'Ballroom · heart-shaped staircase · Salon · Dining and Billiard Rooms · terrace', 2,
         f1, HOUSE_1, HOUSE_1_CLOSED, HOUSE_1_DOORS, HOUSE_1_AMENITIES, HOUSE_1_LABELS),
        ('2', 'House · Floor 2', 'The exhibition, in the former bedrooms', 3, f2, HOUSE_2, HOUSE_2_CLOSED,
         HOUSE_2_DOORS, HOUSE_2_AMENITIES, HOUSE_2_LABELS),
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
                       'doors': doors, **({'homeView': ['Rosecliff', 'Parking', 'Rose Garden']}
                                          if fid == 'G' else {})})
    return {'about': 'Built by tools/build_rosecliff.py. The grounds come from OpenStreetMap (the estate boundary is '
                     'approximate); floors 1 and 2 are traced from Stanford White’s 1902 plans in the McKim, Mead & '
                     'White Monograph (plate 173), turned so north is up. Floor 2 is now the exhibition floor; its '
                     'route may differ from the old bedrooms. The basement has no published plan: only its outline '
                     'is drawn, and the places in it are approximate.',
            'source': 'OpenStreetMap (grounds), A Monograph of the Work of McKim, Mead & White, plate 173 (plans of '
                      'floors 1 and 2), the Preservation Society of Newport County’s accessibility page (visitor '
                      'facilities)',
            'units': f'grounds: metres x {K}, north up; house: pixels of the plate x {S}, turned north up',
            'defaultFloor': '1', 'galleryWord': 'Room', 'floors': floors}


# ---- objects -------------------------------------------------------------------------------------------------------

REC = 'its record in the Preservation Society’s collection'
GUESS = ' (our guess: the Society doesn’t say which room it is in today)'
PLACES = {
    'PSNC.9435': ('Dining Room', f'In the Dining Room ({REC}).', False),
    'PSNC.1572': ('Rose Garden', 'Made for Rosecliff’s garden, where they flanked a path to a fountain (' + REC
                  + ')' + GUESS + '.', True),
    'PSNC.11441': ('Forecourt', 'A fountain figure Theresa Oelrichs owned' + GUESS + '.', True),
}
sys.path.insert(0, str(ROOT / 'tools'))
from harvest_rosecliff import of_rosecliff          # noqa: E402  (which records belong to Rosecliff)
SKIP = set()

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
    return f'data/rosecliff/images/{key}.jpg'



def build_works(floors):
    names = {r['id']: (r['name'], f['id']) for f in floors['floors'] for r in f['rooms']}
    objs = json.loads((CACHE / 'objects.json').read_text())
    objs.pop('_words', None)
    works, extra = [], []
    for r in objs.values():
        if 'images' not in r or not of_rosecliff(r): continue    # not one of Rosecliff's objects
        if r['CAT_NBR'] in SKIP: continue
        key = 'rosecliff-' + re.sub(r'[^a-z0-9]+', '-', r['CAT_NBR'].lower()).strip('-')
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
    return {'museum': MUSEUM, 'name': 'Rosecliff', 'checked': works['checked'],
            'source': 'The Preservation Society of Newport County, Digital Collections', 'onViewKnown': False,
            'note': 'Rosecliff’s furniture, paintings and treasures from the Preservation Society’s Digital '
                    'Collections: objects that name the house or came from its owners, Theresa Fair Oelrichs, who '
                    'built it, and the J. Edgar Monroe family, who gave the house and its contents in 1971. Rosecliff '
                    'is lightly furnished today, and its second floor holds changing exhibitions. Objects without a '
                    'room are in the collection, but the Society doesn’t say where they are shown.',
            'works': rows}


def main():
    if not (CACHE / 'objects.json').exists():
        raise SystemExit('run tools/harvest_rosecliff.py first')
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
