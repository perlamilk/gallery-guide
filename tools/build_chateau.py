#!/usr/bin/env python3
"""Build the Chateau-sur-Mer (Newport, RI) map guide (run: python3 tools/harvest_chateau.py, then this).

    data/chateau/floors.json         the grounds and the two floors of the house on the tour, seen from above (flat 2D)
    data/chateau/artworks.json       the house's objects, each in its room
    data/chateau/images/             their pictures, made smaller for phones
    data/guides/Q5087517.json        the same objects, for the museum page

Where the information comes from
--------------------------------
The map
  - Grounds (floor G): OpenStreetMap (www.openstreetmap.org/api/0.6/map, cached in .cache/chateau/osm.xml): the estate
    (way 1472660184), the walled service yard north of it (1472660193), the house (371945264), the visitor parking
    (1472492429), the drives (19350187, 19349910, 1472660182), the Porter's Lodge (1472492432/33), Bellevue, Leroy and
    Shepard Avenues. Metres east/north of 41.47125 N, 71.30528 W. The Chinese Moon Gate on Shepard Avenue is placed
    from the HABS site plan (sheet 1, "Site plan c. 1917", no. 4): approximate.
  - House floors 1 and 2: traced from the Historic American Buildings Survey's measured drawings (HABS RI-313, 1970;
    public domain; Library of Congress www.loc.gov/item/ri0341/, sheets 5 and 6, master TIFFs 00005a.tif and
    00006a.tif). Units: pixels of those sheets at one fifth size (1927 x 1517); both sheets share the same frame. The
    north arrow points left on the sheets, so we turn them a quarter turn to put north up, like the grounds (checked
    against the HABS text: porte-cochère on the north, dining room east, ballroom south, library west). Room names and
    descriptions follow the HABS data pages (ri0341data.pdf), which call the billiard room "now the morning room" and
    the three-storey stair hall the "tapestry hall".
  - Visitor facilities: the Preservation Society's accessibility page (newportmansions.org page 8855): parking next to
    the house, 9 steps up from the drive, 33 steps to floor 2, no elevator or lift, one restroom (not accessible). HABS
    says the only ground-floor lavatory is off the Billiard Room, so the restroom is put there (probably; the Society
    doesn't say where it is). Floors 3, 4 and the basement are not on the tour and are not drawn.

The objects
  The Preservation Society's Digital Collections (see tools/harvest_chateau.py): objects that name Chateau-sur-Mer or
  came from the Wetmores, who built the house (1852) and lived there until 1966; the Society bought it in 1969. Rooms
  come from each record's own text or the HABS description; objects whose room no source gives are listed on the
  museum page but not put on the map.
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
OUT = ROOT / 'data' / 'chateau'
CACHE = ROOT / '.cache' / 'chateau'
MUSEUM = 'Q5087517'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
COLL = 'https://newportmansions.rediscoverysoftware.com/'
APPROX = 'Approximate'

# ---- grounds (floor G) ----------------------------------------------------------------------------------------------

LAT0, LON0 = 41.47125, -71.30528
K = 2.4                     # map units per metre on the grounds


def G(x, y):
    """Metres east/north of LAT0, LON0 -> map units (north up)."""
    return [round((x + 195) * K, 1), round((172 - y) * K, 1)]


def osm():
    f = CACHE / 'osm.xml'
    if not f.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        url = 'https://www.openstreetmap.org/api/0.6/map?bbox=-71.3080,41.4690,-71.3010,41.4735'
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


def inside(pts, x0=-195, x1=160, y0=-135, y1=172):
    return [p for p in pts if x0 <= p[0] <= x1 and y0 <= p[1] <= y1]


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def grounds(ways):
    rooms = [
        ('Grounds', 'space', 'Chateau-sur-Mer’s park: lawns and rare old trees planted by the Wetmores (a GPS landscape '
                             'tour is in the Newport Mansions app)', ways['1472660184'][:-1]),
        ('Service Yard', 'space', 'The walled yard of the old stables, greenhouses and gardens: not part of the visit',
         ways['1472660193'][:-1]),
        ('Chateau-sur-Mer', 'space', 'Chateau-sur-Mer (1852, enlarged by Richard Morris Hunt in the 1870s): the house '
                                     'tour. Pick floor 1 or 2 above to see the rooms', ways['371945264'][:-1]),
        ('Parking', 'space', 'Visitor parking (free), next to the house; 1 accessible space, 245 ft (75 m) from the '
                             'front door', ways['1472492429'][:-1]),
        ('Drive', 'corridor', 'The drive from the gates on Bellevue Avenue past the house (asphalt)',
         band(ways['19350187'], 3)),
        ('North Drive', 'corridor', 'The loop to the porte-cochère, the front door on the north side of the house',
         band(ways['19349910'], 3)),
        ('Service Drive', 'corridor', 'Service drive to the back lawn (gravel and grass)', band(ways['1472660182'], 2)),
        ('Porter’s Lodge', 'space', 'The Porter’s Lodge (1852) by the north gate', ways['1472492433'][:-1]),
        ('Bellevue Avenue', 'corridor', 'Bellevue Avenue: the north and south gates; RIPTA bus 67 runs along it',
         band(inside(ways['661061476']), 5)),
        ('Leroy Avenue', 'corridor', 'Leroy Avenue', band(inside(ways['19352037']), 4)),
        ('Shepard Avenue', 'corridor', 'Shepard Avenue: the Chinese Moon Gate opens onto it',
         band(inside(ways['19355160']), 4)),
    ]
    doors = [('Bellevue Avenue', 'Drive', (-181, 35)), ('Bellevue Avenue', 'Drive', (-172, -92)),
             ('Drive', 'Parking', (-50, 48)), ('Drive', 'North Drive', (-50, 41)),
             ('North Drive', 'Chateau-sur-Mer', (-8, 17)), ('Drive', 'Grounds', (-32, -10)),
             ('North Drive', 'Service Drive', (15, 33)), ('Grounds', 'Shepard Avenue', (55, -87))]
    amen = [('entrance', -8, 18), ('parking', -52, 66)]
    labels = [('P · Parking (free)', 'area', -52, 88), ('North gate', 'area', -170, 45),
              ('South gate', 'area', -165, -102), ('Front door: porte-cochère, 9 steps up', 'area', -10, 28),
              ('Chinese Moon Gate (approximate)', 'area', 55, -78), ('Back lawn', 'area', 80, 10),
              ('Restroom: inside the house, floor 1', 'area', -5, -25)]
    return rooms, [], doors, amen, labels


# ---- the house -------------------------------------------------------------------------------------------------------
# Units: pixels of HABS sheets 5 and 6 at one fifth size (see the top). On the sheets north is on the left and east at
# the top; R() turns them so north is up.

HABS = 'HABS measured drawings (1970)'
HOUSE_1 = [
    ('Porte-cochère', 'space', 'Porte-cochère on the north side: the front door, 9 steps up to the main floor',
     rect(290, 560, 520, 715), None),
    ('Vestibule', 'space', 'Vestibule: the outer double doors “disappear” into the wall panels; eight low marble steps '
                           'up to the hall', rect(520, 595, 650, 680), None),
    ('Tapestry Hall', 'gallery', 'Great Hall (the “tapestry hall”) and grand stair: three storeys high under a '
                                 'coloured-glass skylight, with Eastlake oak woodwork, bronze figures on the newel '
                                 'posts and a painted Tree of Life climbing the stair',
     [(650, 535), (880, 535), (880, 600), (1105, 600), (1105, 885), (880, 885), (880, 745), (650, 745)],
     'Great Hall'),
    ('Dining Room', 'gallery', 'Dining Room: carved walnut by Luigi Frullini of Florence (1876), gilded leather walls '
                               'and a ceiling painting by Annibale Gatti', rect(885, 220, 1150, 595), 'Dining Room'),
    ('Ballroom', 'gallery', 'Ballroom: part of the 1852 house, redecorated in the 1870s, with mirrored doors and gilt '
                            'plaster', rect(1110, 600, 1500, 850), 'Ballroom'),
    ('Green Parlor', 'gallery', 'Green Parlor (Green Salon): Louis XV style, redone in 1903 by Ogden Codman, with '
                                'green damask walls', rect(1295, 855, 1500, 1090), 'Green Parlor'),
    ('Marble Hall', 'gallery', 'Marble Hall: the original 1852 entrance hall, made into a sitting hall by John '
                               'Russell Pope for George Peabody Wetmore, with walnut woodwork and a stencilled ceiling', rect(1110, 855, 1290, 1250), 'Marble Hall'),
    ('Library', 'gallery', 'Library: carved walnut by Luigi Frullini (dated 1873), with “Colombo” and “Amerigo” on '
                           'the pilasters; one bookcase swings open into the Billiard Room', rect(880, 890, 1105, 1200),
     'Library'),
    ('Billiard Room', 'gallery', 'Billiard Room (later the Morning Room): Eastlake ash panelling and furniture '
                                 'designed by Richard Morris Hunt, Minton tiles of the seasons', rect(600, 745, 875, 1100),
     'Billiard Room'),
    ('Veranda', 'space', 'Veranda along the south side (the Ballroom and Green Parlor open onto it)',
     [(1155, 440), (1665, 440), (1665, 1230), (1300, 1230), (1300, 1100), (1520, 1100), (1520, 580), (1155, 580)],
     None),
]
HOUSE_1_CLOSED = [rect(600, 245, 880, 440), rect(505, 415, 650, 535), rect(650, 440, 880, 535),
                  rect(575, 535, 650, 595)]          # butler's pantry, china closet, service stair, silver vault, linens
HOUSE_1_DOORS = [('Porte-cochère', 'Vestibule', (520, 640)), ('Vestibule', 'Tapestry Hall', (650, 640)),
                 ('Tapestry Hall', 'Dining Room', (1000, 600)), ('Tapestry Hall', 'Ballroom', (1105, 720)),
                 ('Tapestry Hall', 'Library', (1000, 885)), ('Tapestry Hall', 'Billiard Room', (870, 820)),
                 ('Tapestry Hall', 'Marble Hall', (1105, 870)), ('Library', 'Marble Hall', (1105, 1050)),
                 ('Library', 'Billiard Room', (880, 1060)), ('Marble Hall', 'Ballroom', (1200, 850)),
                 ('Marble Hall', 'Green Parlor', (1290, 1150)), ('Ballroom', 'Green Parlor', (1400, 850)),
                 ('Ballroom', 'Veranda', (1500, 720)), ('Dining Room', 'Veranda', (1150, 520))]
HOUSE_1_AMENITIES = [('entrance', 400, 640), ('stairs', 760, 640), ('restroom-all', 645, 710)]
HOUSE_1_LABELS = [('Front door: 9 steps up from the drive', 'area', 230, 520),
                  ('Restroom (the only one in the house, not accessible; place from HABS)', 'area', 470, 900),
                  ('No elevator: 33 steps up to floor 2', 'area', 700, 470),
                  ('North: porte-cochère · South: veranda, lawn · West: Bellevue Avenue', 'area', 1050, 1320)]

HOUSE_2 = [
    ('Upper Hall', 'gallery', 'The balconies of the Great Hall, at the top of the grand stair, under the skylight',
     [(600, 530), (880, 530), (880, 600), (1105, 600), (1105, 890), (880, 890), (880, 745), (600, 745)],
     'Upper Hall'),
    ('Gallery Hall', 'corridor', 'Small galleried hall with a skylight: the upstairs hall of the 1852 house',
     rect(1110, 860, 1290, 1005), None),
    ('Mrs. Wetmore’s Bedroom', 'gallery', 'Mrs. Wetmore’s bedroom (south-east), with its dressing room to the north '
                                         '(Colonial Revival fireplace with old Dutch tiles)',
     rect(1240, 600, 1500, 835), 'Mrs. Wetmore’s Bedroom'),
    ('Dressing Room', 'gallery', 'Mrs. Wetmore’s dressing room and the large tiled bathroom (coloured-glass skylight)',
     rect(1115, 600, 1240, 855), 'Dressing Room'),
    ('Mr. Wetmore’s Bedroom', 'gallery', 'George Peabody Wetmore’s bedroom (south-west): black and red-orange '
                                        'Aesthetic-movement woodwork and a Morris-style paper',
     rect(1295, 840, 1500, 1095), 'Mr. Wetmore’s Bedroom'),
    ('Sitting Room', 'gallery', 'Sitting Room over the original entrance, in the west tower', rect(1125, 1010, 1285, 1250),
     'Sitting Room'),
    ('West Bedroom', 'gallery', 'West bedroom, over the Library, with a white marble fireplace and a cedar closet',
     rect(885, 990, 1110, 1200), 'West Bedroom'),
    ('North-west Bedroom', 'gallery', 'North-west bedroom suite (Hunt, 1870s), over the Billiard Room: wooden '
                                      'fireplaces and stencilled ceilings', rect(615, 855, 880, 1095),
     'North-west Bedroom'),
    ('North Bedroom', 'gallery', 'Small bedroom on the north side, over the Billiard Room', rect(615, 750, 875, 850),
     'Bedroom'),
    ('Nursery', 'gallery', 'The Wetmore children’s nurseries (two rooms), over the Dining Room', rect(890, 220, 1150, 595),
     'Nursery'),
]
HOUSE_2_CLOSED = [rect(615, 245, 880, 520), rect(780, 900, 880, 985)]
HOUSE_2_DOORS = [('Upper Hall', 'Nursery', (1000, 600)), ('Upper Hall', 'Gallery Hall', (1105, 950)),
                 ('Upper Hall', 'North Bedroom', (820, 745)), ('Upper Hall', 'North-west Bedroom', (880, 950)),
                 ('Gallery Hall', 'West Bedroom', (1110, 1000)), ('Gallery Hall', 'Sitting Room', (1200, 1005)),
                 ('Gallery Hall', 'Mr. Wetmore’s Bedroom', (1290, 900)), ('Gallery Hall', 'Dressing Room', (1200, 860)),
                 ('Dressing Room', 'Mrs. Wetmore’s Bedroom', (1240, 680)),
                 ('Mr. Wetmore’s Bedroom', 'Mrs. Wetmore’s Bedroom', (1400, 840))]
HOUSE_2_AMENITIES = [('stairs', 760, 640)]
HOUSE_2_LABELS = [('33 steps up from floor 1 (no elevator)', 'area', 700, 470),
                  ('Rooms from ' + HABS + '; the tour route may differ', 'area', 1050, 1320)]

S = 0.6                 # map units per pixel of the sheets
C = 1400                # turns the sheets: R(x, y) = (C - y, x) puts north (the sheet's left) at the top


def build_floors(ways):
    g_rooms, g_closed, g_doors, g_amen, g_labels = grounds(ways)
    f1 = lambda x, y: [round((C - y) * S, 1), round(x * S, 1)]
    # put the house floors over the house on the grounds map, so switching floors keeps the house in view
    hp = ways['371945264'][:-1]
    hx = sum(p[0] for p in hp) / len(hp)
    hy = sum(p[1] for p in hp) / len(hp)
    cx, cy = f1(1000, 740)
    gx, gy = G(hx, hy)
    shift = (round(gx - cx, 1), round(gy - cy, 1))
    spec = [
        ('G', 'Grounds', 'Parking · gates · lawns and old trees · Chinese Moon Gate', 0, G,
         [(a, b, c, d, None) for a, b, c, d in g_rooms], g_closed, g_doors, g_amen, g_labels),
        ('1', 'House · Floor 1', 'Great Hall · Dining Room · Library · Billiard Room · Ballroom · Green Parlor', 1,
         f1, HOUSE_1, HOUSE_1_CLOSED, HOUSE_1_DOORS, HOUSE_1_AMENITIES, HOUSE_1_LABELS),
        ('2', 'House · Floor 2', 'The Wetmores’ bedrooms, the nurseries and the sitting room', 2, f1, HOUSE_2,
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
                       'doors': doors, **({'homeView': ['Chateau-sur-Mer', 'Parking', 'Porter’s Lodge']}
                                          if fid == 'G' else {})})
    return {'about': 'Built by tools/build_chateau.py. The grounds come from OpenStreetMap; floors 1 and 2 are traced '
                     'from the Historic American Buildings Survey’s measured drawings of 1970 (HABS RI-313), turned so '
                     'north is up, with room names from the HABS description. The restroom’s place comes from HABS '
                     '(the Preservation Society doesn’t say where it is); the Chinese Moon Gate is approximate. Floors '
                     '3, 4 and the basement are not on the tour.',
            'source': 'OpenStreetMap (grounds), Historic American Buildings Survey RI-313 (plans and room '
                      'descriptions of floors 1 and 2), the Preservation Society of Newport County’s accessibility '
                      'page (visitor facilities)',
            'units': f'grounds: metres x {K}, north up; house: pixels of the HABS sheets x {S}, turned north up',
            'defaultFloor': '1', 'galleryWord': 'Room', 'floors': floors}


# ---- objects -------------------------------------------------------------------------------------------------------

REC = 'its record in the Preservation Society’s collection'
GUESS = ' (our guess: the Society doesn’t say which room it is in today)'
PLACES = {
    'PSNC.11552': ('Dining Room', f'Made for this room by Luigi Frullini, and still in place ({REC}).', False),
    'PSNC.11550': ('Library', f'The tiles framing the Library fireplace ({REC}).', False),
    'PSNC.12475': ('Library', 'Made by Frullini for the Library in 1874-76 (' + REC + ')' + GUESS + '.', True),
    'PSNC.11549': ('Billiard Room', f'Set in the fireplace of the Billiard (Morning) Room ({REC}).', False),
    'PSNC.4724': ('Mr. Wetmore’s Bedroom', 'Part of the original furnishings of George Peabody Wetmore’s bedroom ('
                  + REC + ')' + GUESS + '.', True),
}
sys.path.insert(0, str(ROOT / 'tools'))
from harvest_chateau import of_chateau          # noqa: E402  (which records belong to Chateau-sur-Mer)
SKIP = {'PSNC.9804'}            # Watts Sherman silver: came through Annie Wetmore Sherman, not from the house

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
    return f'data/chateau/images/{key}.jpg'



# Rooms and views on the tour, with the Historic American Buildings Survey's photographs (Jack E. Boucher, August 1969;
# public domain; www.loc.gov/item/ri0341/). Key: LOC photo file number, our room, title, text from the HABS data pages.
LOC_PHOTO = 'https://tile.loc.gov/storage-services/service/pnp/habshaer/ri/ri0300/ri0341/photos/{}pv.jpg'
HABS_PHOTOS = [
    (144769, 'Porte-cochère', 'The porte-cochère, from the north-west',
     'Hunt’s porte-cochère on the north side, where visitors arrive: eight low marble steps lead up to the main floor.'),
    (144779, 'Tapestry Hall', 'The grand stair',
     'The open double stair rises three storeys over the entrance. Its underside is painted with foliage that turns '
     'into trellis work and, at the top, a sky with birds; bronze figures by the French foundry Guillaumin stand on '
     'the newel posts, and Charles Salagnad painted the pseudo-tapestry on the walls of the first flights.'),
    (144781, 'Tapestry Hall', 'The skylight and balconies of the Great Hall',
     'Look up: the balconies widen as they rise, so the opening narrows, under a panel of coloured glass that was lit '
     'by gas jets at night and could be opened to air the whole hall.'),
    (144780, 'Tapestry Hall', 'The fireplace of the Great Hall',
     'Minton tiles with caricatures of fish and dogs frame the fireplace; glazed bookcases line the east and west walls.'),
    (144783, 'Billiard Room', 'A light fixture in the Billiard Room',
     'The Billiard Room, later the Morning Room: Eastlake ash panelling, a ceiling of beams meeting in the centre, and '
     'furniture designed by Richard Morris Hunt.'),
    (144784, 'Library', 'The Library, from the west',
     'Luigi Frullini of Florence carved the walnut of the Library and Dining Room; the room was finished late in 1876, '
     'although 1873 is carved over the desk.'),
    (144785, 'Library', 'The Library’s built-in desk, closed',
     'The desk in the middle of the south wall, flanked by pilasters carved with the names Colombo and Amerigo.'),
    (144786, 'Library', 'Carved walnut in the Library', 'A detail of Frullini’s carving.'),
    (144787, 'Dining Room', 'The Dining Room, from the west',
     'Gilded and stamped leather walls, walnut serving tables on caryatids, mirrored doors and shutters, and an oval '
     'ceiling painting of cherubs offering food and drink by Annibale Gatti.'),
    (144788, 'Dining Room', 'The Dining Room overmantel',
     'The curved walnut overmantel with Bacchic cherubs and grapes, over a majolica deer hunt signed E. Glück, 1876.'),
    (144789, 'Green Parlor', 'The Green Parlor, looking west from the Ballroom',
     'Redecorated in the Louis XV style in 1903 by Ogden Codman, a Wetmore relative, with green damask walls.'),
    (144790, 'Mrs. Wetmore’s Bedroom', 'Mrs. Wetmore’s bedroom (south-east), looking north-west',
     'Painted plaster walls framed by mouldings, an oak floor and a heavy wooden mantelpiece on the east wall.'),
]


def habs_rooms(names):
    out = []
    for n, room, title, text in HABS_PHOTOS:
        key = f'chateau-habs-{n}'
        raw = CACHE / 'img' / f'{key}.bin'
        if not raw.exists():
            raw.parent.mkdir(parents=True, exist_ok=True)
            got = subprocess.run(['curl', '-s', '-f', '-m', '90', '-A', UA, LOC_PHOTO.format(n)],
                                 capture_output=True).stdout
            time.sleep(2)
            if got: raw.write_bytes(got)
        dest = OUT / 'images' / f'{key}.jpg'
        if raw.exists() and not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            im = Image.open(io.BytesIO(raw.read_bytes())).convert('RGB')
            im.thumbnail((1000, 1000))
            im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)
        name, floor = names[room]
        out.append({'id': key, 'title': title, 'artist': 'Jack E. Boucher (photograph, 1969)', 'date': '1969',
                    'year': 1969, 'type': 'Room', 'description': text,
                    'credit': 'Historic American Buildings Survey (HABS RI-313), Library of Congress; public domain',
                    'url': 'https://www.loc.gov/item/ri0341/',
                    'image': f'data/chateau/images/{key}.jpg' if dest.exists() else None,
                    'imageCredit': 'Jack E. Boucher, Historic American Buildings Survey (Library of Congress)',
                    'gallery': room, 'galleryName': name, 'floor': floor,
                    'placeNote': 'Photographed in this room in 1969 for the Historic American Buildings Survey.'})
    return [{x: y for x, y in a.items() if y not in (None, '')} for a in out]


def build_works(floors):
    names = {r['id']: (r['name'], f['id']) for f in floors['floors'] for r in f['rooms']}
    objs = json.loads((CACHE / 'objects.json').read_text())
    objs.pop('_words', None)
    works, extra = [], []
    for r in objs.values():
        if 'images' not in r or not of_chateau(r): continue    # not one of Chateau-sur-Mer's objects
        if r['CAT_NBR'] in SKIP: continue
        key = 'chateau-' + re.sub(r'[^a-z0-9]+', '-', r['CAT_NBR'].lower()).strip('-')
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
    works = habs_rooms(names) + works
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
    return {'museum': MUSEUM, 'name': 'Chateau-sur-Mer', 'checked': works['checked'],
            'source': 'The Preservation Society of Newport County, Digital Collections', 'onViewKnown': False,
            'note': 'Chateau-sur-Mer’s furniture, paintings and treasures from the Preservation Society’s Digital '
                    'Collections: objects that name the house or came from the Wetmore family, who built it in 1852 '
                    'and lived there for more than a century. Much of the contents was sold at auction in 1969, when '
                    'the Society bought the house; some pieces have come back since. Objects without a room are in the '
                    'collection, but the Society doesn’t say where they are shown.',
            'works': rows}


def main():
    if not (CACHE / 'objects.json').exists():
        raise SystemExit('run tools/harvest_chateau.py first')
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
