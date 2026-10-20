"""Rebuilds data/floors.json from the MFA visitor map PDF.

    python3 -m venv .venv && .venv/bin/pip install pymupdf numpy pillow
    .venv/bin/python tools/trace_pdf.py path/to/mfa-boston-map.pdf

What it reads from the PDF (all vector data, nothing is traced by eye):
- white shapes  -> public spaces. Shapes with a gallery number become galleries; shapes with
                   a name (Calderwood Courtyard, Taste...) become named spaces; the rest are corridors.
- grey shapes   -> areas closed to visitors (drawn low and dark so the building reads as a whole).
- icons         -> restrooms, elevators, stairs, dining, shop, information, nursing room,
                   accessible entrances, emergency call boxes, water fountains, coat check.
                   Each icon is classified by comparing its picture with the PDF's own legend.
- blue headings -> wing names ("Impressionism", "Dutch and Flemish Art"...).

Everything is written in PDF points; each floor carries a `transform` [scale, dx, dy] that
lines it up with Level 2, because the PDF draws floors in different places and sizes.
Hand decisions live in OVERRIDES below so a new PDF can be traced the same way.
"""
import io, json, re, sys
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'floors.json'

# ---- floors: where each one sits in the PDF and how it lines up with Level 2 ----
G_SCALE = 1 / 0.956  # Levels G/LG are drawn ~4.4% smaller than Level 1
FLOORS = [
    dict(id='G', label='Level G/LG', area='Ground and lower level', order=0, page=1,
         box=(40, 60, 760, 600),
         transform=[G_SCALE, round(311.5 - 313.5 * G_SCALE, 2), round(266 - 245.7 * G_SCALE + 564.4, 2)]),
    dict(id='1', label='Level 1', area='Art of Europe · Italian Renaissance', order=1, page=0,
         box=(40, 60, 760, 620), transform=[1, 0, 564.4]),
    dict(id='2', label='Level 2', area='Art of Europe · Impressionism', order=2, page=0,
         box=(40, 630, 760, 1200), transform=[1, 0, 0]),
    dict(id='3', label='Level 3', area='Art of the Americas', order=3, page=1,
         box=(40, 655, 405, 1085), transform=[1, 358.3, 2.7]),
]

OVERRIDES = {
    # one PDF shape holding two numbered rooms: split at this x (lined up with the floor above/below)
    'split_x': {('146', '145'): 480.6, ('141B', '141A'): 609.7, ('246', '245'): 480.6},
    # rooms that open on start / Recenter
    'home': {
        '2': ['255', '254A', '252', '251', '247', '246', '253', '254', '249', '250'],
        '1': ['155', '152', '153', '154', '148', '146', '145', '144', '143'],
        'G': [],
        '3': [],
    },
    # gallery names seen on collections.mfa.org (the full artwork data adds the rest)
    'names': {
        '252': 'Lorna and Robert Rosenberg Gallery', '255': 'Sidney and Esther Rabb Gallery',
        '253': 'Polly B. and Richard D. Hill Gallery', '251': 'The Beal Gallery', '250': 'William I. Koch Gallery',
        '244': 'Robert and Ruth Remis Gallery', '242': 'Art of the Netherlands in the 17th Century Gallery',
        '144': 'European Art Gallery', '141': 'Italian Renaissance Gallery', '141B': 'Italian Renaissance Gallery',
        '146': 'Rosamund Zander and Hansjörg Wyss Gallery',
        '161': 'Remis Auditorium',   # vertical text in the PDF reads in the wrong order
        '168': None,                 # shares its shape with the Taste café, whose name isn't the gallery's
    },
    # text that names a wing or a whole collection rather than one room
    'areas': ['Art of Europe', 'Art of the Americas', 'Art of Asia', 'Art of Africa', 'Art of Ancient Egypt',
              'Art of Ancient Greece and Rome', 'Modern and Contemporary Art', 'Italian Renaissance',
              'Impressionism', 'Dutch and Flemish Art'],
    'ignore_text': ['Level', 'Levels', 'G/LG', 'Level 1', 'Level 2', 'Level 3', 'get to the',
                    'Center 360), this elevator Level 3.', 'Huntington Avenue'],
    # labels that belong to a specific shape (given by its bounding box) even though another shape overlaps them
    'pin': {'155': (244.8, 102.7, 285.4, 202.3), '158': (95.7, 152.4, 244.8, 202.3)},
    # cleaner names for named spaces
    'rename': {'Japanese Garden Open April through October, weather permitting.': 'Japanese Garden (open April–October)',
               'Sharf Visitor Center · Rotunda': 'Sharf Visitor Center',
               'Shapiro Family Courtyard · New American Café $$': 'Shapiro Family Courtyard · New American Café'},
    # notes the PDF splits into several text runs, placed by hand (PDF points, floor's own drawing)
    'extra_labels': {'1': [dict(text='Conservation Center (Gallery 360): take this elevator to Level 3', kind='note', at=[86.0, 520.0]),
                           dict(text='Taste café', kind='place', at=[160.5, 280.0])]},
}

GALLERY_RE = re.compile(r'^(?:LG|G)?\d{2,3}[A-D]?(?:[–-](?:\d{2,3}|[A-D]))?,?$')


def expand_ids(token):
    """'260–263' -> 260..263, '212A–B' -> 212A, 212B, '159,' -> 159."""
    t = token.rstrip(',')
    m = re.match(r'^(\d{3})[–-](\d{3})$', t)
    if m: return [str(n) for n in range(int(m[1]), int(m[2]) + 1)]
    m = re.match(r'^(\d{3})([A-D])[–-]([A-D])$', t)
    if m: return [m[1] + chr(c) for c in range(ord(m[2]), ord(m[3]) + 1)]
    return [t]
ICON_TYPES = {
    'Stairs': 'stairs', 'Elevator': 'elevator', 'Shop': 'shop', 'Information': 'info',
    'Restrooms': 'restroom', 'Everyone Restrooms': 'restroom-all', 'Nursing Room': 'nursing',
    'Dining': 'dining', 'Accessible Entrance': 'entrance',
}


def is_white(f): return f and min(f) > 0.99
def is_grey(f): return f and abs(f[0] - 0.729) < 0.01


def rings_of(drawing):
    """A drawing can hold several separate outlines; return each closed ring on its own."""
    rings, cur, last = [], [], None
    def flush():
        nonlocal cur
        ring = []
        for p in cur:
            t = [round(p.x, 1), round(p.y, 1)]
            if not ring or ring[-1] != t: ring.append(t)
        if len(ring) > 1 and ring[0] == ring[-1]: ring.pop()
        if len(ring) >= 3: rings.append(ring)
        cur = []
    for it in drawing['items']:
        if it[0] == 're':
            flush(); r = it[1]; cur = [r.tl, r.tr, r.br, r.bl]; flush(); last = None; continue
        if it[0] == 'qu':
            flush(); q = it[1]; cur = [q.ul, q.ur, q.lr, q.ll]; flush(); last = None; continue
        start, end = (it[1], it[2]) if it[0] == 'l' else (it[1], it[4])
        if last is not None and (abs(start.x - last.x) > 0.3 or abs(start.y - last.y) > 0.3):
            flush()
        if not cur: cur.append(start)
        cur.append(end); last = end
    flush()
    return rings


def poly_of(drawing):
    rings = rings_of(drawing)
    return max(rings, key=area) if rings else []


def inside(pt, poly):
    x, y = pt; n = len(poly); c = False
    for i in range(n):
        x1, y1 = poly[i]; x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-9) + x1: c = not c
    return c


def area(poly):
    return abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                   for i in range(len(poly)))) / 2


def text_blocks(page, box):
    """Group words into phrases: same line when close horizontally, same block when stacked."""
    words = [w for w in page.get_text('words') if box[0] < w[0] < box[2] and box[1] < w[1] < box[3]]
    words.sort(key=lambda w: (round(w[1]), w[0]))
    lines = []
    for w in words:
        for ln in lines:
            last = ln[-1]
            same_kind = bool(GALLERY_RE.match(last[4])) == bool(GALLERY_RE.match(w[4]))
            if same_kind and abs(last[1] - w[1]) < 3 and 0 <= w[0] - last[2] < 7 and abs((last[3] - last[1]) - (w[3] - w[1])) < 3:
                ln.append(w); break
        else:
            lines.append([w])
    blocks = []
    for ln in sorted(lines, key=lambda l: l[0][1]):
        x0, y0, x1, y1 = min(w[0] for w in ln), min(w[1] for w in ln), max(w[2] for w in ln), max(w[3] for w in ln)
        text = ' '.join(w[4] for w in ln)
        numeric = all(GALLERY_RE.match(w[4]) for w in ln)
        for b in blocks:
            bx0, by0, bx1, by1 = b['rect']
            if not numeric and not b['numeric'] and -4 <= y0 - by1 < 7 and min(x1, bx1) - max(x0, bx0) > -2 \
                    and abs((y1 - y0) - b['lh']) < 3:
                b['text'] += ' ' + text; b['rect'] = [min(x0, bx0), by0, max(x1, bx1), y1]; break
        else:
            blocks.append(dict(text=text, rect=[x0, y0, x1, y1], numeric=numeric, lh=y1 - y0,
                               words=[(w[4], (w[0] + w[2]) / 2, (w[1] + w[3]) / 2) for w in ln]))
    return blocks


def classify_icons(doc):
    Z = 8
    def crop(page, r, pad=0.5):
        pm = page.get_pixmap(matrix=pymupdf.Matrix(Z, Z), clip=pymupdf.Rect(r.x0 + pad, r.y0 + pad, r.x1 - pad, r.y1 - pad))
        return np.array(Image.open(io.BytesIO(pm.tobytes('png'))).convert('L').resize((40, 40))) < 128
    legend_page = doc[1]
    words = legend_page.get_text('words')
    templates = []
    for x in legend_page.get_drawings():
        r = x['rect']
        if is_white(x.get('fill')) and r.x0 > 415 and r.y0 > 660 and r.y1 < 1010 and 25 < r.width < 45 and 25 < r.height < 45:
            label = ' '.join(w[4] for w in words if r.x1 < w[0] < r.x1 + 80 and r.y0 - 4 < w[1] < r.y1)
            if label in ICON_TYPES: templates.append((ICON_TYPES[label], crop(legend_page, r)))
    # icons the legend drawing above doesn't catch, taken from known examples on the map
    extra = {'emergency': (0, (572.3, 288.3, 592.6, 308.6)), 'water': (1, (419.1, 208.2, 434.6, 223.6)),
             'coat': (0, (395.0, 395.4, 411.1, 411.5)), 'restroom-all': (0, (373.4, 887.0, 389.8, 903.5))}
    for kind, (pi, r) in extra.items():
        templates.append((kind, crop(doc[pi], pymupdf.Rect(*r))))

    icons = []
    for pi, page in enumerate(doc):
        for x in page.get_drawings():
            r = x['rect']
            if not is_white(x.get('fill')) or not (11 < r.width < 23 and 11 < r.height < 23) or abs(r.width - r.height) > 4:
                continue
            if pi == 1 and r.x0 > 415 and r.y0 > 660: continue  # legend
            a = crop(page, r)
            if a.mean() < 0.04: continue  # empty box
            scores = sorted(((float((a & t).sum() / max(1, (a | t).sum())), k) for k, t in templates), reverse=True)
            if scores[0][0] < 0.45: continue  # a small room, not an icon
            c = ((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)
            if any(i['page'] == pi and abs(i['c'][0] - c[0]) < 7 and abs(i['c'][1] - c[1]) < 7 for i in icons):
                continue  # same icon drawn twice (frame + glyph)
            icons.append(dict(page=pi, c=c, type=scores[0][1], score=round(scores[0][0], 2)))
    return icons


def wall_segments(drawings, within):
    """Axis-aligned wall strokes (the thick dark lines). Thin strokes are stair hatching and outlines."""
    segs = []
    for x in drawings:
        if x['type'] not in ('s', 'fs') or not x.get('color') or max(x['color']) > 0.2: continue
        if (x.get('width') or 0) < 0.6 or not within(x['rect']): continue
        for it in x['items']:
            pts = []
            if it[0] == 'l': pts = [(it[1], it[2])]
            elif it[0] == 're':
                r = it[1]; pts = [(r.tl, r.tr), (r.tr, r.br), (r.br, r.bl), (r.bl, r.tl)]
            for p0, p1 in pts:
                if abs(p0.y - p1.y) < 0.6: segs.append(('h', round((p0.y + p1.y) / 2, 1), min(p0.x, p1.x), max(p0.x, p1.x)))
                elif abs(p0.x - p1.x) < 0.6: segs.append(('v', round((p0.x + p1.x) / 2, 1), min(p0.y, p1.y), max(p0.y, p1.y)))
    return segs


def edges_of(poly):
    out = []
    for i in range(len(poly)):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % len(poly)]
        if abs(y0 - y1) < 0.6 and abs(x0 - x1) > 1: out.append(('h', (y0 + y1) / 2, min(x0, x1), max(x0, x1)))
        elif abs(x0 - x1) < 0.6 and abs(y0 - y1) > 1: out.append(('v', (x0 + x1) / 2, min(y0, y1), max(y0, y1)))
    return out


def openings(rooms, walls, min_gap=3.0, tol=1.5):
    """Where two rooms share an edge, the stretches of that edge with no wall drawn are the ways through."""
    edges = [edges_of(r['poly']) for r in rooms]
    found = []
    for i in range(len(rooms)):
        for j in range(i + 1, len(rooms)):
            for d1, c1, a1, b1 in edges[i]:
                for d2, c2, a2, b2 in edges[j]:
                    if d1 != d2 or abs(c1 - c2) > tol: continue
                    lo, hi = max(a1, a2), min(b1, b2)
                    if hi - lo < min_gap: continue
                    c = (c1 + c2) / 2
                    covered = sorted((max(lo, a), min(hi, b)) for d, cc, a, b in walls
                                     if d == d1 and abs(cc - c) <= tol and b > lo and a < hi)
                    gaps, cur = [], lo
                    for a, b in covered:
                        if a - cur >= min_gap: gaps.append((cur, a))
                        cur = max(cur, b)
                    if hi - cur >= min_gap: gaps.append((cur, hi))
                    for g0, g1 in gaps:
                        mid = (g0 + g1) / 2
                        at = [round(mid, 1), round(c, 1)] if d1 == 'h' else [round(c, 1), round(mid, 1)]
                        found.append(dict(a=rooms[i]['id'], b=rooms[j]['id'], at=at, width=round(g1 - g0, 1), axis=d1))
    return found


def overlap_links(rooms, existing):
    """Public shapes drawn on top of each other are one continuous floor: connect them (not drawn on the map)."""
    have = {frozenset((d['a'], d['b'])) for d in existing}
    out = []
    boxes = []
    for r in rooms:
        xs = [p[0] for p in r['poly']]; ys = [p[1] for p in r['poly']]
        boxes.append((min(xs), min(ys), max(xs), max(ys)))
    for i in range(len(rooms)):
        for j in range(i + 1, len(rooms)):
            if frozenset((rooms[i]['id'], rooms[j]['id'])) in have: continue
            (x0, y0, x1, y1), (a0, b0, a1, b1) = boxes[i], boxes[j]
            ox, oy = min(x1, a1) - max(x0, a0), min(y1, b1) - max(y0, b0)
            if ox <= 1 or oy <= 1: continue
            pts = [(max(x0, a0) + ox * u / 5, max(y0, b0) + oy * v / 5) for u in range(1, 5) for v in range(1, 5)]
            shared = [p for p in pts if inside(p, rooms[i]['poly']) and inside(p, rooms[j]['poly'])]
            if len(shared) >= 2:
                cx = sum(p[0] for p in shared) / len(shared); cy = sum(p[1] for p in shared) / len(shared)
                out.append(dict(a=rooms[i]['id'], b=rooms[j]['id'], at=[round(cx, 1), round(cy, 1)], width=0, axis='o', implicit=True))
    return out


def stack_levels(shapes):
    """Shapes that overlap at the same height flicker in 3D; later (topmost) ones get a higher level."""
    boxes = []
    for s in shapes:
        xs = [p[0] for p in s['poly']]; ys = [p[1] for p in s['poly']]
        boxes.append((min(xs), min(ys), max(xs), max(ys)))
    for i, s in enumerate(shapes):
        level = 0
        x0, y0, x1, y1 = boxes[i]
        for j in range(i):
            if shapes[j].get('kind') != s.get('kind'): continue
            a0, b0, a1, b1 = boxes[j]
            ox, oy = min(x1, a1) - max(x0, a0), min(y1, b1) - max(y0, b0)
            if ox <= 1 or oy <= 1: continue
            hits = sum(inside((max(x0, a0) + ox * u / 4, max(y0, b0) + oy * v / 4), s['poly'])
                       and inside((max(x0, a0) + ox * u / 4, max(y0, b0) + oy * v / 4), shapes[j]['poly'])
                       for u in range(1, 4) for v in range(1, 4))
            if hits: level = max(level, shapes[j].get('z', 0) + 1)
        if level: s['z'] = level


def trace(pdf_path):
    doc = pymupdf.open(pdf_path)
    icons = classify_icons(doc)
    floors = []
    for spec in FLOORS:
        page = doc[spec['page']]
        bx = spec['box']
        within = lambda r: r.x0 >= bx[0] and r.x1 <= bx[2] and r.y0 >= bx[1] and r.y1 <= bx[3]
        drawings = page.get_drawings()
        blocks = text_blocks(page, bx)
        icon_here = [i for i in icons if i['page'] == spec['page'] and bx[0] < i['c'][0] < bx[2] and bx[1] < i['c'][1] < bx[3]]

        # icon boxes are white squares too: never treat them as rooms
        def is_icon_box(r):
            c = ((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)
            return r.width < 23 and r.height < 23 and any(abs(i['c'][0] - c[0]) < 8 and abs(i['c'][1] - c[1]) < 8 for i in icon_here)

        # keep drawing order: shapes drawn later sit on top, and a label belongs to the topmost shape under it
        whites = [poly_of(x) for x in drawings if is_white(x.get('fill')) and within(x['rect'])
                  and x['rect'].width > 6 and x['rect'].height > 6 and not is_icon_box(x['rect'])]
        greys = [ring for x in drawings if is_grey(x.get('fill')) and within(x['rect']) and x['rect'].width > 3
                 for ring in rings_of(x)]
        whites = [p for p in whites if len(p) >= 3 and area(p) > 40]

        # white boxes behind words ("Art of Europe", "Shop") are text backgrounds, not rooms:
        # drop them so their text falls through to the space underneath
        def text_box(poly):
            xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
            if len(poly) != 4 or max(ys) - min(ys) > 16: return False
            inner = [bl for bl in blocks if min(xs) - 1 <= bl['rect'][0] and bl['rect'][2] <= max(xs) + 1
                     and min(ys) - 1 <= bl['rect'][1] and bl['rect'][3] <= max(ys) + 1]
            return bool(inner) and not any(bl['numeric'] for bl in inner)
        whites = [p for p in whites if not text_box(p)]

        def bbox_of(poly):
            xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
            return (min(xs), min(ys), max(xs), max(ys))
        pinned = {}
        for label, box in OVERRIDES['pin'].items():
            for i, poly in enumerate(whites):
                if all(abs(a - b) < 0.6 for a, b in zip(bbox_of(poly), box)): pinned[label] = i

        owner = {}
        for b in blocks:
            if b['text'] in OVERRIDES['ignore_text']: continue
            if b['numeric'] and len(b['words']) == 1 and b['words'][0][0] in pinned:
                owner.setdefault(pinned[b['words'][0][0]], []).append(b); continue
            c = ((b['rect'][0] + b['rect'][2]) / 2, (b['rect'][1] + b['rect'][3]) / 2)
            for i in range(len(whites) - 1, -1, -1):
                if inside(c, whites[i]):
                    owner.setdefault(i, []).append(b); break
        used = set()
        rooms = []
        for i, poly in enumerate(whites):
            texts = owner.get(i, [])
            ids = [x for b in texts if b['numeric'] for w in b['words'] for x in expand_ids(w[0])]
            names = [b['text'] for b in texts if not b['numeric'] and b['text'] not in OVERRIDES['areas']]
            for b in texts:
                if b['text'] not in OVERRIDES['areas']: used.add(id(b))
            pair = tuple(ids)
            if len(ids) == 2 and pair in OVERRIDES['split_x']:
                sx = OVERRIDES['split_x'][pair]
                xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
                x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
                for rid, (a, b2) in zip(ids, [(x0, sx), (sx, x1)]):
                    rooms.append(dict(id=rid, kind='gallery', name=OVERRIDES['names'].get(rid),
                                      poly=[[a, y0], [b2, y0], [b2, y1], [a, y1]],
                                      guess=f'One shape in the PDF; split at x={sx} to match the floor above/below.'))
                continue
            if ids:
                rid = ids[0]
                name = OVERRIDES['names'][rid] if rid in OVERRIDES['names'] else (' · '.join(names) or None)
                room = dict(id=rid, kind='gallery', name=name, poly=poly)
                if len(ids) > 1:
                    room['aliases'] = ids[1:]
                    if len(ids) > 1 and not re.search(r'[–-]', ' '.join(w[0] for b in texts if b['numeric'] for w in b['words'])):
                        room['guess'] = 'Several gallery numbers share one shape in the PDF (walls drawn as lines).'
                rooms.append(room)
            elif names:
                slug = re.sub(r'[^a-z0-9]+', '-', names[0].lower()).strip('-')[:30]
                name = ' · '.join(names)
                rooms.append(dict(id=f"{spec['id']}-{slug}", kind='space', name=OVERRIDES['rename'].get(name, name), poly=poly))
            else:
                rooms.append(dict(id=f"{spec['id']}-w{i}", kind='corridor', poly=poly))

        # a shape lying completely inside another is a label background: give its name to the outer one and drop it
        def contains(outer, inner): return all(inside(pt, outer) for pt in inner)
        keep = []
        for r in rooms:
            host = next((o for o in rooms if o is not r and o['kind'] != 'space' and r['kind'] != 'gallery'
                         and area(o['poly']) > area(r['poly']) and contains(o['poly'], r['poly'])), None)
            if host is None:
                keep.append(r); continue
            if r['kind'] == 'space' and host['kind'] == 'corridor':
                host.update(kind='space', id=r['id'], name=r['name'])
        rooms = keep

        # make ids unique (a few corridors can collide with named spaces)
        seen = {}
        for r in rooms:
            if r['id'] in seen:
                seen[r['id']] += 1; r['id'] += f"-{seen[r['id']]}"
            else:
                seen[r['id']] = 0

        closed = [dict(poly=p) for p in greys if len(p) >= 3 and area(p) > 20]

        # leftover text: wing headings and outdoor notes (entrances, garden)
        labels = []
        for b in blocks:
            if id(b) in used or b['text'] in OVERRIDES['ignore_text'] or b['numeric']: continue
            if b['text'].startswith('►') or b['text'].startswith('▶'): b['text'] = b['text'][1:].strip()
            kind = 'area' if b['text'] in OVERRIDES['areas'] else 'note'
            labels.append(dict(text=b['text'], kind=kind,
                               at=[round((b['rect'][0] + b['rect'][2]) / 2, 1), round((b['rect'][1] + b['rect'][3]) / 2, 1)]))

        # wing names written inside rooms would sit on top of gallery numbers; keep only the ones outside
        labels = [l for l in labels if l['kind'] != 'area' or not any(inside(l['at'], r['poly']) for r in rooms)]
        labels += OVERRIDES['extra_labels'].get(spec['id'], [])
        amenities = [dict(type=i['type'], at=[round(i['c'][0], 1), round(i['c'][1], 1)]) for i in icon_here]

        walls = wall_segments(drawings, within)
        doors = openings(rooms, walls)
        doors += overlap_links(rooms, doors)
        stack_levels(rooms)
        for c in closed: c['kind'] = 'closed'
        stack_levels(closed)
        for c in closed: c.pop('kind')

        floors.append(dict(id=spec['id'], label=spec['label'], area=spec['area'], order=spec['order'],
                           transform=spec['transform'], homeView=OVERRIDES['home'].get(spec['id'], []),
                           rooms=rooms, closed=closed, amenities=amenities, labels=labels, doors=doors))

    doc_out = {
        'about': "Traced by tools/trace_pdf.py from the MFA visitor map PDF. Coordinates are PDF points (x right, y down) "
                 "of each floor's own drawing; `transform` [scale, dx, dy] lines the floor up with Level 2. "
                 "Room kinds: gallery (numbered), space (named: courtyards, cafés, shops, auditoriums), corridor. "
                 "`closed` areas are grey on the PDF (not open to visitors). `amenities` come from the map icons.",
        'source': Path(pdf_path).name,
        'units': 'pdf-points',
        'defaultFloor': '2',
        'floors': floors,
    }
    OUT.write_text(json.dumps(doc_out, ensure_ascii=False, indent=1))
    for f in floors:
        kinds = {}
        for r in f['rooms']: kinds[r['kind']] = kinds.get(r['kind'], 0) + 1
        am = {}
        for a in f['amenities']: am[a['type']] = am.get(a['type'], 0) + 1
        print(f"{f['label']}: {kinds}, closed {len(f['closed'])}, labels {len(f['labels'])}, doors {len(f['doors'])}, amenities {am}")


if __name__ == '__main__':
    trace(sys.argv[1] if len(sys.argv) > 1 else 'mfa-boston-map.pdf')
