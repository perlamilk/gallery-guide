"""Builds data/wadsworth/floors.json from the Wadsworth Atheneum's own visitor map PDF.

    python3 -m venv .venv && .venv/bin/pip install pymupdf shapely pillow
    .venv/bin/python tools/trace_wadsworth.py path/to/WAD-FloorMap.pdf [--debug out.png]

The PDF is the "Map and Visitor Guide" linked from thewadsworth.org/visit/planning-your-visit/
(winter 2026 edition: WAD-009-2026_FloorMap_Winter26_MapOnly). One page, drawn sideways, with
Levels 1, 2 and 3 one under the other. Unlike the MFA map it has no gallery numbers: each level is
split into the museum's wings (Avery, Morgan, Wadsworth), each a single coloured shape, and the
legend lists what each wing holds ("AVERY 2: Modernism, Impressionism"). So here a "gallery" is a
wing on one level, named the way the museum signs it ("Avery 2").

What it reads (all vector data, nothing traced by eye):
- orange / yellow / purple shapes -> the Avery, Morgan and Wadsworth wings on that level
- teal shapes   -> named rooms around them (café, shop, library, studio, Hartford Courant Room)
- white shapes  -> the courtyard, offices, attic, light wells: kept as named spaces or closed areas
- dark circles  -> elevators, restrooms, information, café, coat check (by hand, ICONS below)
- legend        -> what each wing holds
Coordinates are PDF points of the page as printed (turned upright), each level shifted so the
three levels line up (the PDF draws them in the same place on their own band).
"""
import json, re, sys
from pathlib import Path

import pymupdf
from shapely.geometry import Polygon, Point, MultiPolygon
from shapely.ops import unary_union, polylabel

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'wadsworth' / 'floors.json'

PAGE_H = 558.0          # the page is stored rotated 90°: upright x = 558 - y, upright y = x - band
LEGEND_Y = 420          # stored y beyond this is the legend column (upright x < 138)
FLOORS = [
    dict(id='1', label='Level 1', band=0, order=1),
    dict(id='2', label='Level 2', band=432, order=2),
    dict(id='3', label='Level 3', band=864, order=3),
]
WINGS = {(0.975, 0.666, 0.562): 'Avery', (1.0, 0.882, 0.5): 'Morgan', (0.607, 0.585, 0.787): 'Wadsworth'}
TEAL = (0.695, 0.871, 0.825)

# icons, by their position on the stored page (top-left corner of the circle, rounded)
ICONS = {
    (991, 199): 'elevator', (1132, 246): 'elevator', (84, 320): 'elevator', (132, 198): 'elevator',
    (274, 247): 'elevator', (700, 246): 'elevator', (558, 198): 'elevator',
    (270, 220): 'coat', (164, 161): 'dining', (327, 287): 'info', (126, 312): 'info',
    (89, 123): 'restroom-all', (553, 131): 'restroom-all',
    (125, 374): 'entrance',
}
OVERRIDES = {
    # white shapes: what they are, by the text inside them
    'white': {'Courtyard': 'space', 'Administrative Offices': 'closed', 'Skylight Attic (no access)': 'closed'},
    # named teal rooms (text inside them)
    'rename': {'Hartford Courant Room': 'Hartford Courant Room', 'Auerbach Art Library': 'Auerbach Art Library',
               'Museum Shop': 'Museum Shop', 'Art Studio': 'Art Studio', 'Café': 'BMuse Café'},
    # text that names a place inside a wing: shown as a label on the floor
    'places': ['Courtyard', 'MATRIX', 'Avery Court', 'Great Hall', 'Video Gallery', 'Gray Court', 'Amistad Center',
               'Cabinet of Art and Curiosity', 'Special Exhibitions', 'The Calm Corner'],
    # notes printed beside the plan
    'notes': ['Stairs from AVERY 1 to THEATER', 'Stairs from MORGAN 2 to AVERY 3', 'Stairs from AVERY 3 to MORGAN 2',
              '600 Main Street Entrance', '29 Atheneum Sq. North Entrance'],
    'ignore': ['Wheelchair accessibility:', 'MAP KEY', 'Wheelchair', 'Accessible Route'],
    # the main entrance has no icon on the plan: put one at the steps, under its label
    'extra_amenities': {'1': [dict(type='entrance', at=[161.0, 297.5])]},
    # rooms that open on start / Recenter
    'home': {'1': [], '2': [], '3': []},
}


def up(x, y, band):
    return (round(PAGE_H - y, 1), round(x - band, 1))


def bezier(p0, p1, p2, p3, n=8):
    out = []
    for k in range(1, n + 1):
        t = k / n; u = 1 - t
        out.append((u**3 * p0.x + 3 * u * u * t * p1.x + 3 * u * t * t * p2.x + t**3 * p3.x,
                    u**3 * p0.y + 3 * u * u * t * p1.y + 3 * u * t * t * p2.y + t**3 * p3.y))
    return out


def rings_of(drawing):
    rings, cur, last = [], [], None
    def flush():
        nonlocal cur
        if len(cur) >= 3: rings.append(cur)
        cur = []
    for it in drawing['items']:
        if it[0] == 're':
            flush(); r = it[1]; rings.append([(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)]); last = None; continue
        if it[0] == 'qu':
            flush(); q = it[1]; rings.append([(q.ul.x, q.ul.y), (q.ur.x, q.ur.y), (q.lr.x, q.lr.y), (q.ll.x, q.ll.y)]); last = None; continue
        start = it[1]
        end = it[2] if it[0] == 'l' else it[4]
        if last is not None and (abs(start.x - last.x) > 0.3 or abs(start.y - last.y) > 0.3): flush()
        if not cur: cur.append((start.x, start.y))
        cur += [(end.x, end.y)] if it[0] == 'l' else bezier(it[1], it[2], it[3], it[4])
        last = end
    flush()
    return rings


def shape_of(drawing):
    """Even-odd: rings inside another ring are holes."""
    polys = [Polygon(r).buffer(0) for r in rings_of(drawing)]
    polys = [p for p in polys if p.area > 1]
    if not polys: return None
    g = polys[0]
    for p in polys[1:]: g = g.symmetric_difference(p)
    return g.buffer(0)


def text_lines(page):
    out = []
    for b in page.get_text('dict')['blocks']:
        for l in b.get('lines', []):
            t = ' '.join(s['text'] for s in l['spans']).strip()
            if not t: continue
            col = pymupdf.sRGB_to_rgb(l['spans'][0]['color'])
            out.append(dict(text=re.sub(r'\s+', ' ', t), rect=l['bbox'], size=round(l['spans'][0]['size']), white=min(col) > 250))
    return out


def phrases(lines):
    """Stack the short lines of one label ("Auerbach / Art / Library") into one phrase."""
    lines = sorted(lines, key=lambda l: (l['rect'][0], l['rect'][1]))
    out = []
    for l in lines:
        x0, y0, x1, y1 = l['rect']
        cy = (y0 + y1) / 2
        for p in out if not l['text'].startswith('Wheelchair accessibility') else []:
            px0, py0, px1, py1 = p['rect']
            if p['size'] == l['size'] and -3 <= x0 - px1 < 4 and abs(cy - (py0 + py1) / 2) < 14 and p['n'] < 4:
                p['text'] += ' ' + l['text']; p['rect'] = (min(x0, px0), min(y0, py0), max(x1, px1), max(y1, py1)); p['n'] += 1
                break
        else:
            out.append(dict(text=l['text'], rect=l['rect'], size=l['size'], white=l['white'], n=1))
    return out


def ring_out(geom, band):
    """Shapely polygon (stored coordinates) -> outer ring and holes in upright coordinates."""
    def conv(coords):
        pts = [list(up(x, y, band)) for x, y in coords][:-1]
        clean = []
        for p in pts:
            if not clean or abs(clean[-1][0] - p[0]) > 0.05 or abs(clean[-1][1] - p[1]) > 0.05: clean.append(p)
        return clean
    geom = geom.simplify(0.25)
    return conv(geom.exterior.coords), [conv(h.coords) for h in geom.interiors if Polygon(h).area > 8]


def parts(geom):
    if geom is None or geom.is_empty: return []
    if isinstance(geom, Polygon): return [geom]
    return [g for g in getattr(geom, 'geoms', []) if isinstance(g, Polygon)]


def legend(lines, band):
    """'AVERY 2' pill followed by what's in that wing, top to bottom (stored x order)."""
    mine = [l for l in lines if band <= l['rect'][0] < band + 432 and l['rect'][1] > LEGEND_Y]
    mine.sort(key=lambda l: l['rect'][0])
    out, cur = {}, None
    for l in mine:
        if l['white'] and re.match(r'^(AVERY|MORGAN|WADSWORTH) \d$', l['text']):
            cur = l['text'].title(); out[cur] = []
        elif cur and l['size'] == 8 and l['text'] not in OVERRIDES['ignore'] and not l['text'].startswith('LEVEL'):
            out[cur].append(l['text'])
    return out


def trace(pdf_path, debug=None):
    doc = pymupdf.open(pdf_path)
    page = doc[0]
    drawings = page.get_drawings()
    lines = text_lines(page)
    floors = []
    for spec in FLOORS:
        band = spec['band']
        def mine(r): return band <= r.x0 and r.x1 <= band + 432 and r.y1 <= LEGEND_Y + 5
        shapes = []   # (order, kind, wing/None, geom)
        for i, d in enumerate(drawings):
            f = d.get('fill')
            if not f or not mine(d['rect']): continue
            key = tuple(round(v, 3) for v in f)
            if key in WINGS: kind = WINGS[key]
            elif key == TEAL: kind = 'teal'
            elif min(f) > 0.99 and d['rect'].width * d['rect'].height > 150 and d['rect'].width * d['rect'].height < 60000: kind = 'white'
            else: continue
            g = shape_of(d)
            if g is not None and g.area > 20: shapes.append((i, kind, g))

        # what's on top wins: cut every shape by the ones drawn after it
        cut = []
        for k, (i, kind, g) in enumerate(shapes):
            above = [g2 for (i2, k2, g2) in shapes[k + 1:] if g2.intersects(g)]
            if above: g = g.difference(unary_union(above)).buffer(0)
            cut.append((i, kind, g))

        texts = phrases([l for l in lines if band <= l['rect'][0] < band + 432 and l['rect'][1] <= LEGEND_Y and not l['white']])
        def text_in(g):
            return [t['text'] for t in texts if g.contains(Point((t['rect'][0] + t['rect'][2]) / 2, (t['rect'][1] + t['rect'][3]) / 2))]

        about = legend(lines, band)
        rooms, closed, labels = [], [], []
        wings = {}
        for i, kind, g in cut:
            if kind in ('Avery', 'Morgan', 'Wadsworth'):
                wings.setdefault(kind, []).append(g)
        for wing, gs in wings.items():
            g = unary_union(gs).buffer(0.3).buffer(-0.3)
            pieces = sorted(parts(g), key=lambda p: -p.area)
            rid = f'{wing} {spec["id"]}'
            holds = about.get(rid, [])
            for n, p in enumerate(pieces):
                if p.area < 60: continue
                poly, holes = ring_out(p, band)
                room = dict(id=rid if n == 0 else f'{rid}-{n}', kind='gallery', label=rid,
                            name=' · '.join(holds) or None, wing=wing, poly=poly)
                if holes: room['holes'] = holes
                lp = polylabel(p, 0.5)
                room['labelAt'] = list(up(lp.x, lp.y, band))
                if n: room['partOf'] = rid
                rooms.append(room)
        for i, kind, g in cut:
            if kind not in ('teal', 'white'): continue
            for p in parts(g):
                if p.area < 60: continue
                words = text_in(p)
                name = ' · '.join(words)
                poly, holes = ring_out(p, band)
                if kind == 'teal':
                    nm = next((OVERRIDES['rename'][w] for w in words if w in OVERRIDES['rename']), name or None)
                    slug = re.sub(r'[^a-z0-9]+', '-', (nm or f'room{i}').lower()).strip('-')[:30]
                    rooms.append(dict(id=f'{spec["id"]}-{slug}', kind='space', name=nm, poly=poly))
                else:
                    role = next((OVERRIDES['white'][w] for w in words if w in OVERRIDES['white']), None)
                    if role == 'space':
                        rooms.append(dict(id=f'{spec["id"]}-' + re.sub(r'[^a-z0-9]+', '-', words[0].lower()), kind='space', name=words[0], poly=poly))
                    elif role == 'closed' or p.area > 400:
                        closed.append(dict(poly=poly))
                    else:
                        closed.append(dict(poly=poly))
        used_names = {r.get('name') for r in rooms} | set(OVERRIDES['rename'])
        for t in texts:
            c = up((t['rect'][0] + t['rect'][2]) / 2, (t['rect'][1] + t['rect'][3]) / 2, band)
            if t['text'] in OVERRIDES['places']:
                labels.append(dict(text=t['text'].title() if t['text'].isupper() else t['text'], kind='place', at=list(c)))
            elif t['text'] in OVERRIDES['notes'] or t['text'].startswith('Stairs from'):
                labels.append(dict(text=t['text'], kind='note', at=list(c)))
            elif t['text'].startswith('Wheelchair accessibility:'):
                labels.append(dict(text=re.sub(r'\s+', ' ', t['text'].replace('Wheelchair accessibility:', 'Wheelchair access:')), kind='note', at=list(c)))

        amenities = []
        for d in drawings:
            r = d['rect']
            key = (round(r.x0), round(r.y0))
            hit = next((t for (x, y), t in ICONS.items() if abs(x - r.x0) < 1.5 and abs(y - r.y0) < 1.5), None)
            if not hit or not mine(r) or not (13 < r.width < 21 and abs(r.width - r.height) < 1.5): continue
            at = list(up((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2, band))
            if any(abs(a['at'][0] - at[0]) < 6 and abs(a['at'][1] - at[1]) < 6 for a in amenities): continue
            amenities.append(dict(type=hit, at=at))
        amenities += OVERRIDES['extra_amenities'].get(spec['id'], [])

        doors = adjacency(rooms)
        area_line = ' · '.join(sorted({r['label'] for r in rooms if r['kind'] == 'gallery'}, key=lambda s: ['Avery', 'Morgan', 'Wadsworth'].index(s.split()[0])))
        floors.append(dict(id=spec['id'], label=spec['label'], area=area_line, order=spec['order'],
                           transform=[1, 0, 0], homeView=OVERRIDES['home'][spec['id']],
                           rooms=rooms, closed=closed, amenities=amenities, labels=labels, doors=doors))

    out = {
        'about': "Traced by tools/trace_wadsworth.py from the Wadsworth Atheneum's visitor map PDF "
                 "(thewadsworth.org, Map and Visitor Guide). Coordinates are PDF points of the upright page, "
                 "each level on its own band, lined up. The map has no gallery numbers: each `gallery` is one wing "
                 "on one level (\"Avery 2\"), `name` lists what the museum's legend says is in it. "
                 "Doors are where shapes touch on the plan, not measured doorways.",
        'source': Path(pdf_path).name,
        'units': 'pdf-points',
        'defaultFloor': '1',
        'galleryWord': '',
        'floors': floors,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    for f in floors:
        kinds = {}
        for r in f['rooms']: kinds[r['kind']] = kinds.get(r['kind'], 0) + 1
        print(f"{f['label']}: {kinds}, closed {len(f['closed'])}, labels {len(f['labels'])}, doors {len(f['doors'])}, "
              f"amenities {[a['type'] for a in f['amenities']]}")
        for r in f['rooms']: print('   ', r['id'], '|', r.get('name'))
    if debug: draw(out, debug)


def adjacency(rooms):
    """Shapes that touch on the plan are connected (the plan doesn't mark doorways)."""
    geoms = []
    for r in rooms:
        try: geoms.append(Polygon(r['poly'], r.get('holes', [])).buffer(0))
        except Exception: geoms.append(Polygon(r['poly']).buffer(0))
    doors = []
    for i in range(len(rooms)):
        for j in range(i + 1, len(rooms)):
            a, b = geoms[i], geoms[j]
            if a.distance(b) > 2.5: continue
            shared = a.buffer(2.5).intersection(b.buffer(2.5))
            if shared.is_empty or shared.area < 6: continue
            c = shared.representative_point()
            w = round(min(25.0, shared.area / 5), 1)
            doors.append(dict(a=rooms[i]['id'], b=rooms[j]['id'], at=[round(c.x, 1), round(c.y, 1)], width=w, axis='o', implicit=True))
    return doors


def draw(doc, path):
    from PIL import Image, ImageDraw
    S = 2
    im = Image.new('RGB', (560 * S, 440 * 3 * S), 'white')
    dr = ImageDraw.Draw(im)
    col = {'Avery': (249, 170, 143), 'Morgan': (255, 225, 128), 'Wadsworth': (155, 149, 200)}
    for k, f in enumerate(doc['floors']):
        oy = k * 440 * S
        P = lambda p: (p[0] * S, p[1] * S + oy)
        for c in f['closed']: dr.polygon([P(p) for p in c['poly']], fill=(200, 200, 200), outline=(120, 120, 120))
        for r in f['rooms']:
            fill = col.get(r.get('wing'), (178, 222, 210) if r['kind'] == 'space' else (240, 240, 240))
            dr.polygon([P(p) for p in r['poly']], fill=fill, outline=(0, 0, 0))
            for h in r.get('holes', []): dr.polygon([P(p) for p in h], fill=(255, 255, 255), outline=(0, 0, 0))
            xs = [p[0] for p in r['poly']]; ys = [p[1] for p in r['poly']]
            dr.text(P((sum(xs) / len(xs), sum(ys) / len(ys))), r.get('label') or r.get('name') or '', fill=(0, 0, 0))
        for d in f['doors']: dr.ellipse([P((d['at'][0] - 2, d['at'][1] - 2)), P((d['at'][0] + 2, d['at'][1] + 2))], fill=(0, 0, 255))
        for a in f['amenities']:
            dr.rectangle([P((a['at'][0] - 4, a['at'][1] - 4)), P((a['at'][0] + 4, a['at'][1] + 4))], fill=(0, 0, 0))
            dr.text(P((a['at'][0] + 5, a['at'][1] - 4)), a['type'], fill=(200, 0, 0))
        for l in f['labels']: dr.text(P(l['at']), l['text'][:40], fill=(0, 120, 0))
    im.save(path)


if __name__ == '__main__':
    args = sys.argv[1:]
    dbg = None
    if '--debug' in args:
        k = args.index('--debug'); dbg = args[k + 1]; del args[k:k + 2]
    trace(args[0] if args else 'wadsworth-map.pdf', dbg)
