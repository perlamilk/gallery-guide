#!/usr/bin/env python3
"""Build the Barnum Museum (Bridgeport, CT) map guide (run: python3 tools/build_barnum.py).

    data/barnum/floors.json     the museum's block of downtown Bridgeport seen from above (flat 2D)
    data/barnum/artworks.json   the façade (on view from the sidewalk) and highlights of the collection
    data/barnum/images/         pictures of the building and of the museum's online exhibits, made smaller for phones
    data/guides/Q4862010.json   the whole catalogue, for the museum page

First run tools/harvest_barnum.py (list, then detail): it reads the museum's catalogue on Connecticut Collections into
.cache/barnum. This script reads OpenStreetMap and a few of the museum's own pages once into the same folder.

The museum is closed
--------------------
The Barnum Institute of Science and History (1893) was damaged by a tornado in 2010 and by Hurricanes Irene and Sandy;
the building is being restored and the museum plans to reopen, as a new museum designed with BRC Imagination Arts, in
2030 (barnum-museum.org, Nov 2026). Nothing is on view inside, and the inside will be rebuilt, so the map does not
guess rooms: it shows the building and its street, the façade you can see from the sidewalk, where to park, the
train station and what is open nearby.

The map
-------
OpenStreetMap (ODbL, api.openstreetmap.org/api/0.6/map, read once into .cache/barnum/osm.xml): the museum (way
206485500, its round front tower on Main Street), Bridgeport Center next door, the parking garages and lots,
the station entrance and platforms and the streets.
True to scale, north up. The front door is the arch under the dome, on Main Street (Carol M. Highsmith's photograph).

Works
-----
  - the façade, on view from the sidewalk: the building (Longstaff & Hurd, 1891-93), the terracotta frieze of
    Bridgeport's history by Henri Plasschaert with its portrait busts, and the dome; pictures cut from Carol M.
    Highsmith's photograph (Library of Congress, public domain)
  - the museum's online exhibits and its latest gift (barnum-museum.org, pictures credited to the museum)
  - collection highlights: the catalogue's objects that have a picture and a curator's description; they are in
    storage while the museum is closed. The museum page lists the whole catalogue (1,002 records).
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

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'barnum'
CACHE = ROOT / '.cache' / 'barnum'
MUSEUM = 'Q4862010'
NAME = 'Barnum Museum'
SITE = 'https://barnum-museum.org'
CTC = 'https://ctcollections.org/index.php'
UA = 'gallery-guide/1.0 (personal museum guide; polite, cached)'
K = 3                                   # map units per metre
LAT0, LON0 = 41.1753, -73.1886
OSM_BBOX = '-73.1915,41.1738,-73.1858,41.1772'
BOX = (-105, -40, 190, 190)            # what the map shows, metres east / north of LAT0, LON0
HIGHSMITH = 'https://tile.loc.gov/image-services/iiif/service:pnp:highsm:13600:13654/full/pct:25/0/default.jpg'
CLOSED = ('The Barnum Museum is closed while its building is restored; it plans to reopen in 2030. This object is in '
          'storage until then: see it online on Connecticut Collections.')


def fetch(url, dest, pause=3):
    if dest.exists() and dest.stat().st_size > 500: return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    for wait in (0, 20, 60):
        time.sleep(wait or pause)
        r = subprocess.run(['curl', '-s', '-L', '-m', '120', '-A', UA, '-w', '%{http_code}', '-o', str(dest), url],
                           capture_output=True, text=True)
        if r.stdout.strip() == '200' and dest.stat().st_size > 500: return True
        dest.unlink(missing_ok=True)
    return False


def P(x, y):
    """Metres east / north of LAT0, LON0 -> map units (north up)."""
    return [round((x - BOX[0]) * K, 1), round((BOX[3] - y) * K, 1)]


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def clip(poly, box):
    """The part of poly inside the rectangle box (Sutherland-Hodgman; the box is convex)."""
    x0, y0, x1, y1 = box
    edges = [(lambda p: p[0] >= x0, lambda a, b: (x0, a[1] + (b[1] - a[1]) * (x0 - a[0]) / (b[0] - a[0]))),
             (lambda p: p[0] <= x1, lambda a, b: (x1, a[1] + (b[1] - a[1]) * (x1 - a[0]) / (b[0] - a[0]))),
             (lambda p: p[1] >= y0, lambda a, b: (a[0] + (b[0] - a[0]) * (y0 - a[1]) / (b[1] - a[1]), y0)),
             (lambda p: p[1] <= y1, lambda a, b: (a[0] + (b[0] - a[0]) * (y1 - a[1]) / (b[1] - a[1]), y1))]
    out = list(poly)
    for inside_, cut in edges:
        src, out = out, []
        for i, cur in enumerate(src):
            prev = src[i - 1]
            if inside_(cur):
                if not inside_(prev): out.append(cut(prev, cur))
                out.append(cur)
            elif inside_(prev):
                out.append(cut(prev, cur))
    pts = []
    for p in out:
        p = (round(p[0], 2), round(p[1], 2))
        if not pts or p != pts[-1]: pts.append(p)
    if len(pts) > 1 and pts[0] == pts[-1]: pts.pop()
    return pts


def band(pts, half):
    left, right = [], []
    for i, (x, y) in enumerate(pts):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, len(pts) - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1
        left.append((x - dy / n * half, y + dx / n * half)); right.append((x + dy / n * half, y - dx / n * half))
    return left + right[::-1]


def inside(pt, poly):
    x, y = pt
    c = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[i - 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c


def osm():
    dest = CACHE / 'osm.xml'
    if not fetch(f'https://api.openstreetmap.org/api/0.6/map?bbox={OSM_BBOX}', dest):
        raise SystemExit('could not read OpenStreetMap')
    r = ET.parse(dest).getroot()
    c = math.cos(math.radians(LAT0))
    nodes = {n.get('id'): (round((float(n.get('lon')) - LON0) * 111320 * c, 2),
                           round((float(n.get('lat')) - LAT0) * 110540, 2)) for n in r.iter('node')}
    ways, streets = {}, {}
    for w in r.iter('way'):
        pts = [nodes[n.get('ref')] for n in w.findall('nd') if n.get('ref') in nodes]
        if len(pts) > 1 and pts[0] == pts[-1]: pts = pts[:-1]
        ways[w.get('id')] = pts
        t = {x.get('k'): x.get('v') for x in w.findall('tag')}
        if t.get('highway') in ('secondary', 'tertiary', 'residential') and t.get('name'):
            streets.setdefault(t['name'], []).append(pts)
    return ways, nodes, streets


def around(p, half):
    return rect(p[0] - half, p[1] - half, p[0] + half, p[1] + half)


def build_floors():
    w, n, streets = osm()
    B = w['206485500']                                     # the museum
    # Main Street (centre line from OpenStreetMap way 659214345) passes the museum's front a little east of north; the
    # sidewalk lies between the road's east edge (4.5 m from the centre line) and the museum's west wall
    def edge(y): return (round(34 - 21 * (y + 36) / 90 + 4.6, 2), y)
    sidewalk = [edge(20), edge(56), (edge(56)[0] + 4, 56), (29.0, 50.4), (26.8, 49.4), (25.4, 47.7), (24.5, 45.8),
                (24.4, 43.3), (24.7, 41.7), (25.9, 40.2), (27.0, 39.2), (27.8, 34.0), (25.8, 33.6), (26.7, 28.7),
                (edge(20)[0] + 4, 20)]
    rooms = [
        ('Barnum Museum', 'gallery', 'The Barnum Museum (the Barnum Institute of Science and History, 1893): closed '
         'while the building is restored, reopening planned for 2030. P. T. Barnum paid for it; inside are kept some '
         '60,000 objects about Barnum, Bridgeport and 19th-century America', B, 'Barnum Museum (closed)'),
        ('Façade', 'gallery', 'Main Street sidewalk in front of the museum: look up at the terracotta frieze of '
         'Bridgeport’s history and its portrait busts, the dome and the corner tower; the front door is the arch under '
         'the dome', sidewalk, 'Façade'),
        ('Bridgeport Center', 'space', 'Bridgeport Center, the white office tower next door (Richard Meier, 1989)',
         w['206485515'], None),
        ('Ralph n Rich’s', 'space', 'Ralph ’n’ Rich’s, an Italian restaurant across Main Street',
         around(n['4013623475'], 6), None),
        ('Garage Water Street', 'space', 'Parking garage (public, paid)', w['398622304'], None),
        ('Lot Cesar Batalla', 'space', 'Parking lot (paid)', w['1333079087'], None),
        ('Lot Broad Street', 'space', 'Parking lot (paid)', w['327502778'], None),
        ('Station entrance', 'space', 'Bridgeport station: Metro-North New Haven Line, Amtrak and CTrail Shore Line '
         'East trains, the Greater Bridgeport Transit buses and the Port Jefferson ferry close by',
         around(n['13997880264'], 7), None),
        ('Platforms', 'space', 'Bridgeport station platforms', clip(w['327414425'], BOX), None),
    ]
    for name, half in (('Main Street', 4.5), ('State Street', 5), ('John Street', 5), ('Broad Street', 5),
                       ('Cesar Batalla Way', 4), ('Bank Street', 4), ('Water Street', 6), ('Lafayette Boulevard', 6)):
        for i, line in enumerate(streets.get(name, [])):
            poly = clip(band(line, half), BOX)
            if len(poly) >= 3:
                rid = name if i == 0 else f'{name} {i + 1}'
                if any(r[0] == rid for r in rooms): continue
                rooms.append((rid, 'corridor', name, poly, None))
    doors = [('Façade', 'Barnum Museum', (24.6, 44.5))]
    amen = [('entrance', 25.2, 43.5), ('dining', n['4013623475'][0], n['4013623475'][1]),
            ('entrance', *n['13997880264'])]
    labels = [('Closed for restoration · reopening 2030', 60, 30),
              ('Main Street', 4, 95), ('↑ Bridgeport Center (white tower)', 60, 70),
              ('Seaside Park and Barnum’s statue: about 2 km southwest ↙', -60, -30),
              ('Station →', 130, 150)]
    rooms = [(rid, kind, name, clip(poly, BOX), short) for rid, kind, name, poly, short in rooms]
    rr = []
    for rid, kind, name, poly, short in rooms:
        assert len(poly) >= 3, rid
        r = {'id': rid, 'kind': kind, 'name': name, 'poly': [P(*q) for q in poly]}
        if kind == 'gallery': r['label'] = short
        rr.append(r)
    fl = {'id': '1', 'label': 'Main Street', 'order': 0, 'transform': [1, 0, 0],
          'area': 'The museum (closed until 2030) · the façade from the sidewalk · parking · Bridgeport station',
          'rooms': rr, 'closed': [],
          'amenities': [{'type': t, 'at': P(x, y)} for t, x, y in amen],
          'labels': [{'text': t, 'kind': 'note', 'at': P(x, y)} for t, x, y in labels],
          'doors': [{'a': a, 'b': b, 'at': P(*p), 'width': 14, 'axis': 'o'} for a, b, p in doors]}
    ids = [r['id'] for r in rr]
    assert len(ids) == len(set(ids))
    for d in fl['doors']:
        assert d['a'] in ids and d['b'] in ids, d
    for am in fl['amenities']:
        assert any(inside(am['at'], r['poly']) for r in rr), am
    return {'about': 'Built by tools/build_barnum.py. The museum is closed while its 1893 building is restored '
                     '(reopening planned for 2030), so the map shows the building and its street from above, traced '
                     'from OpenStreetMap, true to scale, north up: the façade you can see from the sidewalk, parking, '
                     'the train station and what is nearby. No rooms inside are drawn: they are being rebuilt.',
            'source': 'OpenStreetMap (the museum, streets, parking, station); the front door from Carol M. '
                      'Highsmith’s photograph (Library of Congress)',
            'units': f'metres x {K}, north up', 'approximate': False, 'defaultFloor': '1', 'galleryWord': 'Place',
            'floors': [fl]}


# ---- pictures ---------------------------------------------------------------------------------------------------------

def save(key, im):
    if im.mode != 'RGB': im = im.convert('RGB')
    im.thumbnail((1000, 1000))
    dest = OUT / 'images' / f'{key}.jpg'
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, 'JPEG', quality=80, optimize=True, progressive=True)
    return f'data/barnum/images/{key}.jpg'


def picture(key, url, crop=None):
    from PIL import Image
    raw = CACHE / 'img' / (re.sub(r'[^A-Za-z0-9._-]', '_', url.split('/')[-1] if 'loc.gov' not in url else
                                  'highsmith.jpg'))
    if not fetch(url, raw): return None
    im = Image.open(io.BytesIO(raw.read_bytes()))
    if crop:
        W, H = im.size
        im = im.crop((int(crop[0] * W), int(crop[1] * H), int(crop[2] * W), int(crop[3] * H)))
    return save(key, im)


HS_CREDIT = 'Carol M. Highsmith, Library of Congress (public domain)'
# key, title, artist, date, type, description, crop of Highsmith's photograph
FACADE = [
    ('building', 'The Barnum Institute of Science and History', 'Longstaff & Hurd, architects', '1891–1893',
     'Architecture',
     'P. T. Barnum paid for this building in the last year of his life, as a home for the Bridgeport Scientific '
     'Society, the Fairfield County Historical Society and the Bridgeport Medical Society; it opened on February 18, '
     '1893, two years after his death. The Bridgeport architects Longstaff & Hurd mixed Romanesque and Byzantine: '
     'brownstone below, red brick and terracotta above, a round tower crowned by a tiled dome at the front and a '
     'pointed tower at the corner. Barnum wanted shops on the ground floor to pay for its upkeep. It is the last '
     'building in Bridgeport tied to Barnum, and became a National Historic Landmark in 2023. Since a tornado in 2010 '
     'and the hurricanes that followed it has been under restoration.', None),
    ('frieze', 'Frieze of Bridgeport’s history, with portrait busts', 'Henri Plasschaert, sculptor', 'about 1893',
     'Sculpture',
     'Around the dome runs a terracotta frieze in five scenes: Native American (1670), Early Settler (1760), Maritime '
     '(1840), Civil War (1861) and Industrial Revolution (1870). Between them are busts of a Native American, '
     'Christopher Columbus, George Washington, Elias Howe, Winfield Scott and Grover Cleveland. Look up from the '
     'sidewalk in front of the door.', (0.30, 0.25, 0.73, 0.40)),
    ('inscription', '“Barnum Institute of Science and History”', 'Longstaff & Hurd, architects', '1893',
     'Architecture',
     'The building’s first name, in raised letters across the front, above a band of terracotta ornament and below the windows of the dome. The '
     'societies Barnum built it for later merged, and the building became the Barnum Museum; from 1946 into the 1960s '
     'it was an annex of City Hall.', (0.12, 0.50, 0.86, 0.70)),
]

# the museum's online exhibits and its latest gift (barnum-museum.org, read Nov 5, 2026)
ONLINE = [
    ('seeley-hat', 'The Seeley beaver hat', 'Bridgeport hatmaker', 'about 1850', 'Object',
     'a-family-heirloom-finds-a-new-home-the-seeley-beaver-hat-comes-to-the-barnum-museum',
     '2026/10/1000047661_web.jpg',
     'A beaver-fur top hat with the label of a Bridgeport hatmaker, worn by Henry Seeley and handed down in the '
     'Seeley family for five generations before it was given to the museum in October 2026. Barnum’s daughter '
     'Pauline married Nathan Seeley in the 1860s.'),
    ('widow-priest-mummy', 'The Widow, the Priest, and the Mummy', 'Online exhibit', '2023', 'Exhibit',
     'the-widow-the-priest-and-the-mummy', '2023/06/Digital-Exhibit.jpg',
     'The museum’s first all-digital exhibit, about its Egyptian mummy and the people who brought it to Bridgeport, '
     'with short videos by experts and pages to explore; there is an Educator Guide too.'),
    ('ipy', 'Ipy’s mummy', 'Research project', 'about 4,000 years old', 'Exhibit', 'ipys-mummy',
     '2023/06/BarnumMuseum_MummyEducatorGuide.jpg',
     'Ipy, an Egyptian mummy some 4,000 years old, has been studied for several years by an international team; the '
     'films (“Discovering Ipy’s Mummy”, and “Uncovering the Secrets of an Egyptian Mummy and Coffin”, which won two '
     'Telly awards) are on the museum’s YouTube channel.'),
    ('becoming-barnum', 'Becoming Barnum', 'Podcast', '1847 letters', 'Exhibit', 'becoming-barnum',
     '2024/11/becoming-barnum-1-scaled.jpg',
     'A podcast following Barnum through the copybook of letters he kept in 1847, from blogs by Curator Emerita '
     'Adrienne Saint-Pierre.'),
]


# ---- the collection (Connecticut Collections) --------------------------------------------------------------------------

def one(v):
    v = re.sub(r'\s+', ' ', v or '').strip(' ,;')
    for sep in (';', ', '):
        parts = [p.strip() for p in v.split(sep)]
        if len(parts) % 2 == 0 and parts[:len(parts) // 2] == parts[len(parts) // 2:]:
            v = sep.join(parts[:len(parts) // 2])
    seen, out = set(), []
    for p in [p.strip() for p in v.split(', ')]:
        if p and p.lower() not in seen: seen.add(p.lower()); out.append(p)
    return ', '.join(out)


def unit(s, label):
    m = re.search(r'<!--\s*<label>' + label + r'</label>\s*-->(.*?)</div>', s, re.S)
    return m.group(1) if m else ''


def plain(s):
    s = re.sub(r'<br\s*/?>|</p>', '\n', s)
    t = html.unescape(re.sub(r'<[^>]+>', '', s)).replace('\xa0', ' ')
    return re.sub(r'[ \t]+', ' ', '\n'.join(l.strip() for l in t.split('\n') if l.strip()))


def detail(oid):
    f = CACHE / 'detail' / f'{oid}.html'
    if not f.exists(): return {}
    s = f.read_text(encoding='utf-8', errors='ignore')
    d = {}
    m = re.search(r'<H1>(.*?)</H1>', s, re.S)
    if m: d['title'] = one(plain(m.group(1)))
    makers = re.findall(r'<a href="/index.php/Detail/entities/\d+">([^<]+)</a>\s*\(([^)]+)\)', s)
    who = [nm.strip() for nm, role in makers if re.search(r'creat|artist|maker|manufact|photograph|paint|design|'
                                                         r'engrav|print|publish|sculpt', role, re.I)]
    if who: d['artist'] = ', '.join(dict.fromkeys(who))
    m = re.search(r'<div class="unit">([^<]*?)\(Date [^)]*\)', s)
    if m: d['date'] = m.group(1).strip()
    d['medium'] = one(plain(unit(s, 'Medium')))
    d['material'] = one(plain(unit(s, 'Material')))
    desc = plain(unit(s, 'Description'))
    if desc: d['description'] = desc
    m = re.search(r"https:(?:\\/|/){2}ctcollections\.org(?:\\/|/)media[^'\"\s]+?_large\.jpg", s)
    if m: d['image'] = m.group(0).replace('\\/', '/')
    return {k: v for k, v in d.items() if v}


def year(date):
    m = re.search(r'1[5-9]\d\d|20[0-2]\d', date or '')
    return int(m.group()) if m else None


def split_title(t):
    """'Photograph: General Tom Thumb as Napoleon' -> ('Photograph', 'General Tom Thumb as Napoleon')."""
    m = re.match(r'([A-Z][A-Za-z ,&/-]{2,40}):\s+(.+)', t or '')
    return (m.group(1).strip(), m.group(2).strip()) if m else (None, (t or '').strip())


def build_works(floors):
    names = {r['id']: r['name'] for f in floors['floors'] for r in f['rooms']}
    works, rows = [], []
    for key, title, artist, date, typ, text, crop in FACADE:
        img = picture('bm-' + key, HIGHSMITH, crop)
        works.append({'id': 'bm-' + key, 'title': title, 'artist': artist, 'date': date, 'year': year(date),
                      'type': typ, 'description': text, 'url': 'https://www.loc.gov/item/2011631848/',
                      'image': img, 'imageCredit': HS_CREDIT, 'gallery': 'Façade', 'galleryName': names['Façade'],
                      'floor': '1'})
    for key, title, artist, date, typ, path, photo, text in ONLINE:
        img = picture('bm-' + key, f'{SITE}/wp-content/uploads/{photo}')
        a = {'id': 'bm-' + key, 'title': title, 'artist': artist, 'date': date, 'type': typ,
             'description': text + '\n\n' + 'Online at barnum-museum.org; the museum itself is closed until 2030.',
             'url': f'{SITE}/{path}/', 'image': img, 'imageCredit': 'The Barnum Museum (barnum-museum.org)',
             'gallery': 'Barnum Museum', 'galleryName': names['Barnum Museum'], 'floor': '1', 'placeGuessed': True,
             'placeNote': 'In the museum’s collection or online; the building is closed until 2030.'}
        works.append({k: v for k, v in a.items() if v not in (None, '')})
    objs = json.loads((CACHE / 'objects.json').read_text())
    highlights = 0
    for o in objs:
        d = detail(o['oid'])
        kind, title = split_title(d.get('title') or one(o['title']))
        title = re.sub(r'\s*\((?:owned by|on loan to) the Barnum Museum\)', '', title, flags=re.I) or 'Untitled'
        typ = kind or {'Physical Object': 'Object', 'Still Image': 'Picture'}.get(o['kind'], o['kind'])
        medium = ', '.join(x for x in (d.get('medium'), d.get('material')) if x)
        row = {'id': 'bm-' + o['oid'], 'title': title, 'artist': d.get('artist') or 'Unknown maker',
               'date': d.get('date'), 'year': year(d.get('date')), 'medium': medium or None, 'type': typ,
               'url': f'{CTC}/Detail/objects/{o["oid"]}', 'imageUrl': d.get('image') or o.get('thumb'),
               'onView': False, 'accession': (o['acc'] or '').strip() or None}
        rows.append({k: v for k, v in row.items() if v not in (None, '')})
        label = d.get('description', '')
        if row.get('imageUrl') and len(label) > 250 and o['kind'] in ('Still Image', 'Physical Object'):
            highlights += 1
            a = {'id': row['id'], 'title': title, 'artist': row['artist'], 'date': row.get('date'),
                 'year': row.get('year'), 'type': typ, 'medium': medium or None,
                 'description': label + '\n\n' + CLOSED, 'url': row['url'], 'image': row['imageUrl'],
                 'accession': row.get('accession'), 'imageCredit': 'The Barnum Museum, via Connecticut Collections',
                 'gallery': 'Barnum Museum', 'galleryName': names['Barnum Museum'], 'floor': '1',
                 'placeGuessed': True, 'placeNote': 'In storage while the museum is closed (reopening 2030).'}
            works.append({k: v for k, v in a.items() if v not in (None, '')})
    for wk in reversed(works[:len(FACADE) + len(ONLINE)]):
        rows.insert(0, {k: v for k, v in {'id': wk['id'], 'title': wk['title'], 'artist': wk['artist'],
                        'date': wk['date'], 'type': wk['type'], 'url': wk['url'], 'imageUrl': wk.get('image'),
                        'onView': wk['gallery'] == 'Façade', 'gallery': wk['gallery'], 'floor': '1'}.items() if v})
    by = {r['id']: r for r in rows}
    for wk in works:
        if wk['id'] in by: by[wk['id']].update(gallery=wk['gallery'], floor=wk['floor'])
    read = sum(1 for o in objs if (CACHE / 'detail' / (o['oid'] + '.html')).exists())
    print(f'{len(works)} on the map ({highlights} collection highlights), {len(rows)} on the museum page, '
          f'{read} object pages read')
    return works, rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    floors = build_floors()
    (OUT / 'floors.json').write_text(json.dumps(floors, ensure_ascii=False, separators=(',', ':')))
    works, rows = build_works(floors)
    checked = time.strftime('%Y-%m-%d')
    source = 'The Barnum Museum (barnum-museum.org) and its catalogue on Connecticut Collections (ctcollections.org)'
    (OUT / 'artworks.json').write_text(json.dumps({'source': source, 'checked': checked, 'count': len(works),
                                                   'complete': False, 'artworks': works},
                                                  ensure_ascii=False, separators=(',', ':')))
    guide = {'museum': MUSEUM, 'name': NAME, 'checked': checked, 'source': source, 'onViewKnown': True,
             'note': 'The Barnum Museum is closed while its building is restored (reopening planned for 2030), so '
                     'nothing inside is on view. Its catalogue on Connecticut Collections lists 1,002 records '
                     '(General Tom Thumb and Lavinia Warren, Jenny Lind, Barnum’s homes, circus photographs, '
                     'Bridgeport history); about 60,000 objects in all. On view: only the façade, from the sidewalk.',
             'works': rows}
    (ROOT / 'data' / 'guides' / f'{MUSEUM}.json').write_text(json.dumps(guide, ensure_ascii=False,
                                                                         separators=(',', ':')))
    idx_path = ROOT / 'data' / 'guides.json'
    idx = json.loads(idx_path.read_text())
    idx['museums'][MUSEUM] = {'works': len(rows), 'pictures': sum(bool(w.get('imageUrl')) for w in rows),
                              'onView': sum(bool(w.get('onView')) for w in rows), 'galleries': True,
                              'checked': checked, 'source': source}
    idx_path.write_text(json.dumps(idx, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    sys.exit(main())
