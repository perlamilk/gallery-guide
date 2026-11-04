#!/usr/bin/env python3
"""Build the Harvard Art Museums map guide (run: python3 tools/build_harvard_map.py).

Harvard publishes one plan per floor at harvardartmuseums.org/visit/floor-plan/<n>: a drawing of the
floor and, on top of it, one SVG shape per room, in the same pixel coordinates, with the room's
number and name. This turns them into the map guide's format (the same as data/floors.json for the
MFA and data/wadsworth/floors.json), shown as a flat 2D plan in guide.html?museum=harvard:

  data/harvard/floors.json    floors, rooms (gallery numbers), amenities, doors
  data/harvard/artworks.json  the works on view, from data/guides/Q3783572.json
                              (run tools/build_guides.py Q3783572 first, with HARVARD_API_KEY)

The drawing's icons (restrooms, elevators, stairs, café, shop, entrances) aren't in the SVG, so
their places are written below by hand, read off Harvard's floor drawings.
Doors: the plan doesn't mark doorways, so rooms whose shapes nearly touch are connected.

Pages are fetched one at a time with a pause between them.
"""
import html
import json
import os
import re
import time
import urllib.request
from datetime import date

from shapely.geometry import Polygon

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'harvard')
MUSEUM = 'Q3783572'
BASE = 'https://harvardartmuseums.org'
UA = 'GalleryGuidePersonal/1.0 (personal, non-commercial museum guide app)'

# Floor id, label, what is there, and [scale, dx, dy]: each drawing has its own size, so this lines
# the floors up on Level 2's drawing (through the elevators and stairs, which sit in the same place
# on every floor), at 0.3 size so a floor fits a phone screen like the Wadsworth's plan.
FLOORS = [
    ('0', 'Lower Level', 'Lecture halls · Materials Lab · Coatroom', [0.51, 15, 3]),
    ('1', 'Level 1', 'Entrance · Courtyard · Modern & Contemporary · Asian · Shop · Café', [0.3, 0, -16.5]),
    ('2', 'Level 2', 'European & American · Asian · Islamic · Medieval', [0.3, 0, 0]),
    ('3', 'Level 3', 'Ancient Mediterranean & Middle East · Egypt · Special Exhibitions', [0.3, 0, 0]),
    ('4', 'Level 4', 'Art Study Center (by appointment)', [0.3, 84.9, 42.6]),
    ('5', 'Level 5', 'Lightbox Gallery · Conservation labs', [0.3, 93.3, 46.8]),
]

# Read off Harvard's drawings (pixel coordinates of each floor's drawing).
AMENITIES = {
    '0': [('restroom', 257, 352), ('restroom', 385, 352), ('elevator', 384, 236), ('stairs', 322, 236),
          ('entrance', 135, 188), ('coat', 258, 66)],
    '1': [('entrance', 597, 1035), ('entrance', 597, 95), ('entrance', 165, 95), ('entrance', 1215, 1045),
          ('info', 382, 720), ('coat', 857, 720), ('dining', 845, 640), ('shop', 340, 640),
          ('restroom', 357, 797), ('restroom', 828, 797), ('elevator', 711, 470),
          ('stairs', 597, 470), ('stairs', 296, 785), ('stairs', 897, 785)],
    '2': [('restroom', 357, 740), ('restroom', 833, 740), ('elevator', 711, 418),
          ('stairs', 597, 420), ('stairs', 296, 735), ('stairs', 897, 735)],
    '3': [('restroom', 362, 742), ('restroom', 833, 742), ('elevator', 711, 418),
          ('stairs', 597, 420), ('stairs', 296, 735), ('stairs', 897, 735)],
    '4': [('restroom', 116, 425), ('restroom', 521, 425), ('elevator', 428, 272), ('stairs', 320, 272)],
    '5': [('elevator', 398, 256), ('stairs', 298, 256)],
}
LABELS = {'1': [('Admissions', 'place', 462, 720), ('Main entrance · Quincy Street', 'note', 597, 1060),
                ('Prescott Street entrance', 'note', 597, 30)]}

# Halls and entrances the SVG leaves out (they hold the stairs and restrooms), drawn from the plans so
# that directions can get from one wing to the other, and passages the plan shows but no shape covers.
def _hall(dy=0):
    west = [[278, 687 + dy], [409, 687 + dy], [409, 758 + dy], [457, 758 + dy], [457, 830 + dy], [278, 830 + dy]]
    east = [[734, 758 + dy], [785, 758 + dy], [785, 687 + dy], [916, 687 + dy], [916, 830 + dy], [734, 830 + dy]]
    return west, east


_w1, _e1 = [[278, 741], [409, 741], [409, 700], [457, 700], [457, 885], [278, 885]], \
    [[734, 700], [785, 700], [785, 741], [916, 741], [916, 885], [734, 885]]
EXTRA_ROOMS = {
    '1': [('1-west', 'West Hall', _w1), ('1-east', 'East Hall', _e1),
          ('1-quincy', 'Quincy Street Entrance', [[522, 885], [676, 885], [676, 990], [522, 990]]),
          ('1010', 'Prescott Street Entrance', [[522, 215], [624, 215], [624, 535], [522, 535]])],
    '2': [('2-west', 'West Hall', _hall()[0]), ('2-east', 'East Hall', _hall()[1])],
    '3': [('3-west', 'West Hall', _hall()[0]), ('3-east', 'East Hall', _hall()[1])],
}
EXTRA_DOORS = {
    '1': [('1740', '1610', 428, 347), ('1440', '1500', 768, 347), ('1010', '1600', 522, 300), ('1010', '1520', 624, 300)],
    '2': [('2740', '2600', 378, 293), ('2440', '2540', 768, 293)],
    '3': [('3740', '3610', 378, 293), ('3440', '3500', 768, 293)],
}

# rooms that are passages, not galleries
CORRIDOR = re.compile(r'Arcade|Lobby|Entrance|Entryway|Reception', re.I)


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=60) as res:
        data = res.read()
    time.sleep(1)
    return data


def text(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s))).strip()


def svg_polys(d):
    """The plan's paths use M, h, v, H, V and z only: straight walls."""
    polys, pts, x, y = [], [], 0.0, 0.0
    for cmd, args in re.findall(r'([MmHhVvLlZz])([^MmHhVvLlZz]*)', d):
        nums = [float(n) for n in re.findall(r'-?\d*\.?\d+(?:e-?\d+)?', args)]
        if cmd in 'Zz':
            if pts: polys.append(pts)
            pts = []
            continue
        if cmd in 'MmLl':
            for i in range(0, len(nums), 2):
                x, y = (nums[i], nums[i + 1]) if cmd.isupper() else (x + nums[i], y + nums[i + 1])
                if cmd in 'Mm' and i == 0 and pts:
                    polys.append(pts); pts = []
                pts.append([x, y])
        elif cmd in 'Hh':
            for n in nums: x = n if cmd == 'H' else x + n; pts.append([x, y])
        elif cmd in 'Vv':
            for n in nums: y = n if cmd == 'V' else y + n; pts.append([x, y])
    if pts: polys.append(pts)
    return [p for p in polys if len(p) >= 3]


def floor_rooms(n):
    page = get(f'{BASE}/visit/floor-plan/{n}').decode('utf-8')
    svg = max(re.findall(r'<svg[^>]*>.*?</svg>', page, re.S), key=len)
    names = {}
    for m in re.finditer(r'<li x-on:click="current = \'([^\']+)\'(.*?)</li>', page, re.S):
        spans = [text(s) for s in re.findall(r'<span class="ifp-room-info__(?:room|title)[^"]*">(.*?)</span>', m.group(2), re.S)]
        names[m.group(1)] = [s for s in spans if not s.startswith('Room ')]
    rooms = []
    for rid, d in re.findall(r'x-on:click="current = \'([^\']+)\'[^>]*?\sd="([^"]+)"', svg):
        spans = names.get(rid, [])
        name = spans[-1] if spans else rid
        if n == '1' and rid == 'A':
            rid = '1000'   # the courtyard: works list it as gallery 1000
        polys = svg_polys(d)
        biggest = max(polys, key=lambda p: Polygon(p).area)
        kind = 'gallery' if re.fullmatch(r'\d{4}', rid) and not CORRIDOR.search(name) else \
            'corridor' if CORRIDOR.search(name) else 'space'
        r = {'id': rid if re.fullmatch(r'\d{4}', rid) else f'{n}-{rid}', 'kind': kind, 'name': name,
             'poly': [[round(x, 1), round(y, 1)] for x, y in biggest]}
        if kind != 'gallery':
            r['label'] = name
        if len(spans) > 1:
            r['area'] = spans[0]
        rooms.append(r)
    return rooms


def adjacency(rooms, gap=14):
    """Rooms whose shapes nearly touch on the plan are connected (the plan has no doorways)."""
    geoms = [Polygon(r['poly']).buffer(0) for r in rooms]
    doors = []
    for i in range(len(rooms)):
        for j in range(i + 1, len(rooms)):
            a, b = geoms[i], geoms[j]
            if a.distance(b) > gap:
                continue
            shared = a.buffer(gap / 2 + 1).intersection(b.buffer(gap / 2 + 1))
            if shared.is_empty or shared.area < 40:
                continue
            c = shared.representative_point()
            doors.append({'a': rooms[i]['id'], 'b': rooms[j]['id'], 'at': [round(c.x, 1), round(c.y, 1)],
                          'width': round(min(40.0, shared.area / (gap + 2)), 1), 'axis': 'o', 'implicit': True})
    return doors


def floors_doc():
    floors = []
    for order, (n, label, area, transform) in enumerate(FLOORS):
        rooms = floor_rooms(n)
        have = {r['id'] for r in rooms}
        rooms += [{'id': rid, 'kind': 'corridor', 'name': name, 'poly': poly}
                  for rid, name, poly in EXTRA_ROOMS.get(n, []) if rid not in have]
        doors = adjacency(rooms) + [{'a': a, 'b': b, 'at': [x, y], 'width': 30, 'axis': 'o', 'implicit': True}
                                    for a, b, x, y in EXTRA_DOORS.get(n, [])]
        floors.append({
            'id': n, 'label': label, 'area': area, 'order': order, 'transform': transform,
            'rooms': rooms, 'closed': [],
            'amenities': [{'type': t, 'at': [x, y]} for t, x, y in AMENITIES.get(n, [])],
            'labels': [{'text': t, 'kind': k, 'at': [x, y]} for t, k, x, y in LABELS.get(n, [])],
            'doors': doors,
        })
        print(f'  {label}: {len(rooms)} rooms, {len(floors[-1]["doors"])} connections')
    return {
        'about': 'Built by tools/build_harvard_map.py from the Harvard Art Museums floor plans '
                 f'({BASE}/visit/floor-plan). Coordinates are pixels of each floor\'s drawing; transform lines '
                 'the floors up. Amenities were placed by hand from the drawings. Doors are where shapes nearly '
                 'touch, not measured doorways.',
        'source': f'{BASE}/visit/floor-plan', 'units': 'pixels', 'defaultFloor': '1', 'galleryWord': 'Gallery',
        'floors': floors,
    }


def artworks_doc(rooms):
    guide = json.load(open(os.path.join(ROOT, 'data', 'guides', f'{MUSEUM}.json'), encoding='utf-8'))
    out = []
    for w in guide['works']:
        if not w.get('onView'):
            continue
        a = {'id': w['id'], 'title': w['title'], 'artist': w.get('artist', ''), 'date': w.get('date', ''),
             'medium': w.get('medium', ''), 'accession': w.get('accession', ''), 'onView': True,
             'type': w.get('type', ''), 'culture': w.get('culture', ''), 'gallery': w['gallery'],
             'galleryName': w.get('galleryName') or rooms.get(w['gallery'], ''), 'floor': w['floor'],
             'url': w.get('url', '')}
        if w.get('year') is not None:
            a['year'] = w['year']
        if w.get('imageUrl'):
            a['image'] = w['imageUrl']                 # Harvard's server, which allows showing it
            a['imageCredit'] = w.get('imageCredit', 'Harvard Art Museums')
        out.append({k: v for k, v in a.items() if v not in (None, '')} | {'onView': True})
    return {'source': 'Harvard Art Museums API (works in a gallery today)', 'checked': guide['checked'],
            'count': len(out), 'complete': True, 'artworks': out}


def main():
    print('Harvard Art Museums floor plans…')
    os.makedirs(OUT, exist_ok=True)
    floors = floors_doc()
    rooms = {r['id']: r['name'] for f in floors['floors'] for r in f['rooms']}
    art = artworks_doc(rooms)
    missing = sorted({a['gallery'] for a in art['artworks']} - set(rooms))
    if missing:
        print(f'  works in galleries not on the plan: {missing}')
    for name, doc in [('floors.json', floors), ('artworks.json', art)]:
        with open(os.path.join(OUT, name), 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
    print(f'  {art["count"]} works on view. Next: python3 tools/build_pack.py, and bump VERSION in sw.js.')


if __name__ == '__main__':
    main()
