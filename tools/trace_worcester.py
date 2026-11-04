"""Builds data/worcester/floors.json from the Worcester Art Museum's own visitor map PDF.

    python3 -m venv .venv && .venv/bin/pip install pymupdf shapely pillow opencv-python-headless numpy
    .venv/bin/python tools/trace_worcester.py path/to/wam-visitor-map.pdf [--debug folder]

The PDF is the floor map linked from worcesterart.org/visit/floor-map/ (June 2026 edition:
wam-visitor-map-060326.pdf). One page; the building is drawn as a tall stack of levels seen from
above at an angle (an isometric view): walls run at 30° and 150°. This turns each level back into a
flat plan seen from straight above, which is what the app shows (Grazi asked for 2D maps):

- isometric -> plan: a point (x, y) on the page is (u, v) on the plan, where x = cos30·(u + v) and
  y = sin30·(v − u). Each level is drawn higher up the page than the one below it, so its y is first
  shifted by that level's offset (DY, measured on the elevator shafts that run through every level).
- floor: the light grey top faces of each level (vector fills), painted in the PDF's own order.
- walls: the thin grey strokes. Doorways are gaps in them, so every wall is stretched across short
  gaps to close each room, then the room is filled from its gallery number printed inside it.
  Rooms whose shapes meet where there was no wall are connected by a door there.
- icons (elevators, stairs, restrooms, café, shop, coat room) are found as the round black icons
  on the page and named by hand (ICONS below, by their order top to bottom).
Everything comes from the PDF's vector data; only the icon names and the room names were read by eye.
"""
import json, math, re, sys
from pathlib import Path

import cv2
import numpy as np
import pymupdf
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'worcester' / 'floors.json'
SOURCE = 'https://www.worcesterart.org/visit/floor-map/'

C, S = math.cos(math.radians(30)), 0.5
K = 4                     # raster pixels per plan unit while tracing
MAP_X = 380               # the plan is right of this on the page; the legend is to the left
# page y of each level's band, and how far up the page it is drawn (from the elevator shafts)
FLOORS = [
    dict(id='0', label='Ground Level', band=(990, 1200), dy=0.0, order=0,
         area='Renaissance Court · Asian · Roman · Medieval · Café · Shop · Salisbury St. entrance'),
    dict(id='1', label='Level 1', band=(800, 990), dy=181.3, order=1,
         area='Egyptian Art · Special Exhibitions · Earle Hall'),
    dict(id='2', label='Level 2', band=(515, 800), dy=363.3, order=2,
         area='European Art · Arms and Armor · Special Exhibitions · Lancaster St. entrance · Library'),
    dict(id='3', label='Level 3', band=(345, 515), dy=546.3, order=3,
         area='American Art · Higgins Education Wing studios'),
    dict(id='4', label='Level 4', band=(200, 345), dy=755.5, order=4,
         area='Modern & Contemporary Art · Jeppson Idea Lab'),
]
TOP = {(0.813, 0.811, 0.805), (0.732, 0.734, 0.735), (0.693, 0.696, 0.699), (0.652, 0.657, 0.664),
       (0.824, 0.829, 0.828)}
SIDE = (0.591, 0.597, 0.606)
WALL = (0.591, 0.597, 0.606)
BLACK = (0.013, 0.019, 0.02)

# gallery names, from the map's legend and worcesterart.org/visit/floor-map/
NAMES = {
    '0001': 'Asian Jade and Ceramic Art', '0002': 'Chinese and Korean Art', '0003': 'Japanese Art',
    '0004': 'West, South, and Southeast Asian Art', '0008': 'Roman Art', '0009': 'Medieval Chapter House',
    '0010': 'Medieval Art', '0011': 'Medieval Art',
    '1000': 'Egyptian Art', '1102': 'Special Exhibition · Lower Frances L. Hiatt Gallery',
    '1104': 'Print Study Room (by appointment)', '1200': 'Stephen Earle Hall',
    '2001': 'European Art (14th–15th c.)', '2002': 'European Art (14th–16th c.)',
    '2003': 'European Art (15th–16th c.)', '2004': 'European Art (16th–17th c.)', '2005': 'European Art (17th c.)',
    '2006': 'European Art (16th–18th c.)', '2007': 'European Art (17th c.) · Daniels Gallery',
    '2008': 'European Art (18th–19th c.) · Robert W. Booth Gallery',
    '2009': 'European Art (18th–19th c.) · Morgan Gallery', '2010': 'European Art (19th–20th c.)',
    '2011': 'European Art (19th–20th c.)', '2102': 'Special Exhibition · Upper Frances L. Hiatt Gallery',
    '2200': 'Stephen Salisbury Hall', '2201': 'Special Exhibition · Jean and Myles McDonough Gallery',
    '2202': 'Arms and Armor', '2204': 'Arms and Armor', '2404': 'Family Nook', '2410': 'Studio',
    '2413': 'Hoche-Scofield Room', '2416': 'Studio', '2417': 'Studio', '2418': 'Open Door Gallery',
    '2419': 'Library',
    '3000': 'American Art · Louisa Dresser Gallery', '3001': 'American Art', '3002': 'American Art',
    '3003': 'American Art · John and Linda Nelson Gallery', '3401': 'Studio', '3406': 'Computer Lab',
    '3410': 'Conference Room', '3411': 'Studio', '3412': 'Studio', '3413': 'Studio', '3414': 'Studio',
    '4001': 'Modern Art · James Corcoran Donnelly Gallery', '4002': 'Contemporary Art · Sidney and Rosalie Rose Gallery',
    '4003': 'Jeppson Idea Lab',
}
SPACES = re.compile(r'Studio|Computer Lab|Conference|Family Nook|Library|Print Study|Idea Lab|Hoche')
# rooms named in words on the plan, not numbered: (floor, id, name, page point inside it)
NAMED = [
    ('0', '0-court', 'Renaissance Court', (686, 1071)), ('0', '0-lobby', 'Salisbury Lobby', (704, 1084)),
    ('2', '2200', 'Stephen Salisbury Hall', (617, 672)), ('2', '2-lancaster-room', 'Lancaster Room', (595, 643)),
    ('2', '2-lobby', 'Lancaster Lobby', (634, 620)), ('2', '2418', 'Open Door Gallery', (456, 614)),
    ('2', '2419', 'Library', (430, 621)), ('1', '1200', 'Stephen Earle Hall', (623, 847)),
]
# walls the PDF leaves open but that bound a gallery: (floor, from, to) in the output's coordinates.
# Gallery 2007 is the corner of the walk around the light well; this closes it off from the walk.
EXTRA_WALLS = {'2': [((204.5, 326.0), (214.6, 326.0))]}
CORRIDOR_IDS = {'0-court', '0-lobby', '2-lobby'}
# the round icons, top to bottom (see the --debug contact sheet); None = not an amenity the app shows
ICONS = ['elevator', 'stairs', 'elevator', 'stairs', 'restroom-all', 'restroom', 'stairs', 'elevator',
         'stairs', 'elevator', 'stairs', 'restroom', 'restroom-all', 'stairs', 'coat', None,
         'elevator', 'stairs', 'elevator', 'elevator', 'stairs', 'elevator', 'elevator', 'elevator',
         'restroom', 'restroom-all', 'restroom', 'elevator', 'stairs', 'elevator', 'elevator', 'restroom-all',
         'coat', 'dining', 'shop']
# entrances (page points) and notes printed beside the plan
ENTRANCES = {'0': [(712, 1100)], '1': [(676, 812)], '2': [(682, 624)]}
LABELS = {
    '0': [('Salisbury St. entrance', 'note', (735, 1112))],
    '1': [('Lancaster St. entrance', 'note', (700, 822)), ('Not an exit', 'note', (556, 881))],
    '2': [('Lancaster St. entrance', 'note', (702, 634)), ('Stoddard Garden Courtyard', 'place', (511, 638))],
    '4': [('This level has artworks with flashing and strobe effects', 'note', (610, 240))],
}


def rnd(c): return tuple(round(v, 3) for v in (c or ()))


def plan(pt, dy):
    x, y = pt[0], pt[1] + dy
    return ((x / C - y / S) / 2, (x / C + y / S) / 2)


def path_points(d):
    """The outlines of a filled path, one list of points per closed sub-path."""
    subs, pts = [], []
    for it in d['items']:
        if it[0] in 'lc':
            a, b = it[1], it[-1]
            if pts and math.hypot(a.x - pts[-1][0], a.y - pts[-1][1]) > 0.05:
                subs.append(pts); pts = []
            if not pts: pts.append((a.x, a.y))
            if it[0] == 'c': pts.append((it[2].x, it[2].y)); pts.append((it[3].x, it[3].y))
            pts.append((b.x, b.y))
        elif it[0] == 're':
            r = it[1]; subs.append([(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)])
        elif it[0] == 'qu':
            q = it[1]; subs.append([(q.ul.x, q.ul.y), (q.ur.x, q.ur.y), (q.lr.x, q.lr.y), (q.ll.x, q.ll.y)])
    if pts: subs.append(pts)
    return [s for s in subs if len(s) > 2]


def square(pts):
    """False for a shape whose edges mostly run at slants: a shadow or light well, not a floor."""
    good = bad = 0.0
    for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]):
        L = math.hypot(bx - ax, by - ay)
        a = math.degrees(math.atan2(by - ay, bx - ax)) % 45
        if 3 < a < 42: bad += L
        else: good += L
    return bad < 0.3 * (good + bad)


def floor_of(y):
    return next((f for f in FLOORS if f['band'][0] < y <= f['band'][1]), None)


def read_page(pdf):
    page = pymupdf.open(pdf)[0]
    per = {f['id']: dict(fills=[], walls=[]) for f in FLOORS}
    for d in page.get_drawings():
        r = d['rect']
        if r.x0 < MAP_X: continue
        f = floor_of((r.y0 + r.y1) / 2)
        if not f: continue
        if 'f' in d['type']:
            subs = [[plan(p, f['dy']) for p in pts] for pts in path_points(d)]
            if subs: per[f['id']]['fills'].append((rnd(d['fill']), subs, r.width * r.height))
        if d['type'] == 's' and rnd(d['color']) == WALL:
            for it in d['items']:
                if it[0] == 'l':
                    per[f['id']]['walls'].append((plan((it[1].x, it[1].y), f['dy']), plan((it[2].x, it[2].y), f['dy'])))
    words = [w for w in page.get_text('words') if w[0] > MAP_X]
    icons = []
    for d in page.get_drawings():
        r = d['rect']
        if r.x0 > MAP_X and 'f' in d['type'] and 8.3 < r.width < 9.2 and 8.3 < r.height < 9.2 and rnd(d['fill']) == BLACK:
            c = ((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)
            if all(abs(c[0] - a) + abs(c[1] - b) > 2 for a, b in icons): icons.append(c)
    icons.sort(key=lambda c: (c[1], c[0]))
    return page, per, words, icons


def extend_walls(walls, img, maxlen):
    """Stretch each wall end along its direction until it meets another wall (closes doorways)."""
    h, w = img.shape
    out = img.copy()
    for a, b in walls:
        ax, ay, bx, by = a[0] * K, a[1] * K, b[0] * K, b[1] * K
        L = math.hypot(bx - ax, by - ay)
        if L < 2: continue
        ux, uy = (bx - ax) / L, (by - ay) / L
        for (sx, sy, dx, dy) in ((bx, by, ux, uy), (ax, ay, -ux, -uy)):
            path = []
            for t in range(3, int(maxlen * K)):
                x, y = int(round(sx + dx * t)), int(round(sy + dy * t))
                if not (0 <= x < w and 0 <= y < h): path = []; break
                path.append((x, y))
                if img[y, x]:
                    break
            else:
                path = []
            if path:
                cv2.line(out, (int(sx), int(sy)), path[-1], 255, 2)
    return out


def trace_floor(fid, data, seeds, origin):
    x0, y0, W, H = origin
    T = lambda p: (int(round((p[0] - x0) * K)), int(round((p[1] - y0) * K)))
    floor = np.zeros((H, W), np.uint8)
    for col, subs, area in data['fills']:         # painted in the PDF's order, like the page
        if col in TOP: subs = [s for s in subs if square(s)]   # a slanted shape is a shadow, not a floor
        shape = np.zeros_like(floor)              # sub-paths inside others are holes (even-odd)
        for pts in subs:
            one = np.zeros_like(floor)
            cv2.fillPoly(one, [np.array([T(p) for p in pts], np.int32)], 255)
            shape ^= one
        if col in TOP: floor[shape > 0] = 255
        elif col == SIDE and area > 30: floor[shape > 0] = 0
        elif col == (1.0, 1.0, 1.0): floor[shape > 0] = 255 if area < 220 else 0
    floor = cv2.morphologyEx(floor, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    walls = np.zeros_like(floor)
    for a, b in data['walls']:
        cv2.line(walls, T(a), T(b), 255, 2)
    closed = extend_walls([(((a[0] - x0), (a[1] - y0)), ((b[0] - x0), (b[1] - y0))) for a, b in data['walls']], walls, 16)
    for a, b in EXTRA_WALLS.get(fid, []):
        cv2.line(closed, (int(a[0] * K), int(a[1] * K)), (int(b[0] * K), int(b[1] * K)), 255, 2)
    free = cv2.bitwise_and(floor, cv2.bitwise_not(closed))
    n, lab = cv2.connectedComponents(free, connectivity=4)
    regions = {}
    for rid, name, pt in seeds:
        if rid in regions: continue
        px, py = T(pt)
        best = None
        for r in range(0, 12):
            for ddx in range(-r, r + 1):
                for ddy in (-r, r) if abs(ddx) != r else range(-r, r + 1):
                    x, y = px + ddx, py + ddy
                    if 0 <= x < W and 0 <= y < H and lab[y, x]:
                        best = lab[y, x]; break
                if best: break
            if best: break
        if best and best not in regions.values():
            regions[rid] = best
        elif best:
            print(f'  level {fid}: {rid} shares a space with {[k for k, v in regions.items() if v == best]}')
        else:
            print(f'  level {fid}: no space found for {rid}')
    # every other space on the floor big enough to walk through is a hall
    sizes = np.bincount(lab.ravel())
    k = 0
    for i in range(1, n):
        if i in regions.values() or sizes[i] < 60 * K * K: continue
        k += 1; regions[f'{fid}-hall{k}'] = i

    def poly_of(i):
        m = (lab == i).astype(np.uint8) * 255
        m = cv2.dilate(m, np.ones((3, 3), np.uint8))          # back over half the wall
        cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        c = max(cs, key=cv2.contourArea)
        c = cv2.approxPolyDP(c, 1.2, True)
        return [[round(p[0][0] / K, 1), round(p[0][1] / K, 1)] for p in c], m

    rooms, masks = [], {}
    for rid, i in regions.items():
        poly, m = poly_of(i)
        if len(poly) < 3: continue
        masks[rid] = m
        rooms.append((rid, poly))
    # doors: where two spaces meet across a gap the original walls left open
    walls_d = cv2.dilate(walls, np.ones((3, 3), np.uint8))
    doors = []
    ids = list(masks)
    for a in range(len(ids)):
        ma = cv2.dilate(masks[ids[a]], np.ones((5, 5), np.uint8))
        for b in range(a + 1, len(ids)):
            mb = cv2.dilate(masks[ids[b]], np.ones((5, 5), np.uint8))
            touch = cv2.bitwise_and(cv2.bitwise_and(ma, mb), cv2.bitwise_not(walls_d))
            cnt = cv2.countNonZero(touch)
            if cnt < 4 * K: continue
            ys, xs = np.nonzero(touch)
            j = len(xs) // 2
            order = np.lexsort((ys, xs))
            px, py = xs[order[j]], ys[order[j]]
            doors.append({'a': ids[a], 'b': ids[b], 'at': [round(px / K, 1), round(py / K, 1)],
                          'width': round(min(12.0, cnt / K / 3), 1), 'axis': 'o', 'implicit': True})
    # a space the walls shut off entirely still opens somewhere: join it to the neighbour it shares most with
    linked = {d['a'] for d in doors} | {d['b'] for d in doors}
    for a in ids:
        if a in linked: continue
        ma = cv2.dilate(masks[a], np.ones((7, 7), np.uint8))
        best = max(((cv2.countNonZero(cv2.bitwise_and(ma, masks[b])), b) for b in ids if b != a), default=(0, None))
        if best[0] < 3 * K: continue
        ys, xs = np.nonzero(cv2.bitwise_and(ma, masks[best[1]]))
        j = len(xs) // 2
        doors.append({'a': a, 'b': best[1], 'at': [round(xs[j] / K, 1), round(ys[j] / K, 1)], 'width': 6.0,
                      'axis': 'o', 'implicit': True})
        linked |= {a, best[1]}
    return rooms, doors, floor, closed, lab


def main():
    pdf = sys.argv[1]
    debug = sys.argv[sys.argv.index('--debug') + 1] if '--debug' in sys.argv else None
    page, per, words, icons = read_page(pdf)
    if len(icons) != len(ICONS):
        sys.exit(f'{len(icons)} icons on the page, {len(ICONS)} named: the PDF changed, check the contact sheet')
    allp = [p for f in per.values() for _, subs, _ in f['fills'] for pts in subs for p in pts]
    x0, y0 = min(p[0] for p in allp) - 4, min(p[1] for p in allp) - 4
    W = int((max(p[0] for p in allp) - x0 + 8) * K); H = int((max(p[1] for p in allp) - y0 + 8) * K)
    floors = []
    for f in FLOORS:
        fid = f['id']
        seeds = [(rid, name, plan(pt, f['dy'])) for nf, rid, name, pt in NAMED if nf == fid]
        for w in words:
            cx, cy = (w[0] + w[2]) / 2, (w[1] + w[3]) / 2
            if re.fullmatch(r'\d{4}', w[4]) and floor_of(cy) is f and w[4][0] == fid:
                seeds.append((w[4], NAMES.get(w[4], w[4]), plan((cx, cy), f['dy'])))
        rooms, doors, floor_img, closed, lab = trace_floor(fid, per[fid], seeds, (x0, y0, W, H))
        linked = {d['a'] for d in doors} | {d['b'] for d in doors}
        closed_areas = [{'poly': poly} for rid, poly in rooms if rid not in linked]   # staff rooms, shafts
        rooms = [(rid, poly) for rid, poly in rooms if rid in linked]
        out_rooms = []
        for rid, poly in rooms:
            # shift to the page origin of the trace (all floors share it, so they line up)
            name = NAMES.get(rid) or next((n for _, i, n, _ in NAMED if i == rid), None)
            if rid in CORRIDOR_IDS or name is None:
                kind = 'corridor'
            elif re.fullmatch(r'\d{4}', rid) and not SPACES.search(name):
                kind = 'gallery'
            else:
                kind = 'space'
            r = {'id': rid, 'kind': kind, 'name': name or 'Hall', 'poly': poly}
            if kind != 'gallery' and name: r['label'] = name.split(' (')[0]
            out_rooms.append(r)
        P = lambda pt: [round(v, 1) for v in (plan(pt, f['dy'])[0] - x0, plan(pt, f['dy'])[1] - y0)]
        amen = []
        for (cx, cy), kind in zip(icons, ICONS):
            if kind and floor_of(cy) is f: amen.append({'type': kind, 'at': P((cx, cy))})
        for pt in ENTRANCES.get(fid, []): amen.append({'type': 'entrance', 'at': P(pt)})
        labels = [{'text': t, 'kind': k, 'at': P(pt)} for t, k, pt in LABELS.get(fid, [])]
        floors.append(dict(id=fid, label=f['label'], area=f['area'], order=f['order'], transform=[1, 0, 0],
                           rooms=out_rooms, closed=closed_areas, amenities=amen, labels=labels, doors=doors))
        g = sum(1 for r in out_rooms if r['kind'] == 'gallery')
        print(f"  {f['label']}: {len(out_rooms)} spaces ({g} galleries), {len(doors)} doors, {len(amen)} amenities")
        if debug:
            img = cv2.cvtColor(floor_img // 3, cv2.COLOR_GRAY2BGR)
            rng = np.random.default_rng(1)
            for r in out_rooms:
                col = tuple(int(c) for c in rng.integers(80, 255, 3))
                pts = np.array([[int(x * K), int(y * K)] for x, y in r['poly']], np.int32)
                cv2.fillPoly(img, [pts], col)
                cx, cy = pts.mean(0).astype(int)
                cv2.putText(img, r['id'], (int(cx) - 20, int(cy)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
            img[closed > 0] = (0, 0, 255)
            for d in doors:
                cv2.circle(img, (int(d['at'][0] * K), int(d['at'][1] * K)), 6, (0, 200, 0), -1)
            for a in amen:
                cv2.circle(img, (int(a['at'][0] * K), int(a['at'][1] * K)), 9, (255, 0, 0), 2)
                cv2.putText(img, a['type'][:4], (int(a['at'][0] * K) + 10, int(a['at'][1] * K)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
            ys, xs = np.nonzero(floor_img)
            Path(debug).mkdir(parents=True, exist_ok=True)
            cv2.imwrite(f'{debug}/level{fid}.png', img[max(0, ys.min() - 40):ys.max() + 40, max(0, xs.min() - 40):xs.max() + 40])
    doc = {
        'about': 'Built by tools/trace_worcester.py from the Worcester Art Museum visitor map PDF '
                 f'({SOURCE}). The PDF draws the levels in an isometric view; here they are turned back into '
                 'flat plans seen from above. Rooms are closed across doorways; doors are where spaces meet '
                 'without a wall. Icons were named by hand.',
        'source': SOURCE, 'units': 'points', 'defaultFloor': '2', 'galleryWord': 'Gallery', 'floors': floors,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(',', ':')))
    print(f'wrote {OUT.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
