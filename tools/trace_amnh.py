#!/usr/bin/env python3
"""Trace the five levels of the American Museum of Natural History from its own visitor map (run once:
python3 tools/trace_amnh.py).

    tools/data/amnh-trace.json   rooms (polygons), closed areas, doorways and amenity icons per level, in map units

The map: the museum's English visitor map (amnh.org/content/download/385996/5752508/file/english-map.pdf, made in
InDesign, August 2026, "© 2026"). Pages 2-6 are Floors 4, 3, 2, 1 and the Lower Level, all drawn on the same frame
(elevators and stairs line up). Walls are black, areas the public can't enter are grey. Pages are rendered at 200 dpi.
The building is everything inside the outer wall; each room grows from a seed point (SEEDS: where its name is printed,
or by hand for hallways) until it meets walls, grey or another room (watershed), so rooms follow the drawn walls.
Where the map draws no wall between two halls, the line between them is where the two growing rooms meet (a guess).
Amenity icons (restrooms, elevators, stairs, escalators, dining, shops, information, tickets...) are found by matching
the icons of each page's own legend against the plan. Map units: PDF points x 2 (the page is 576 x 648 pt), Central
Park West at the bottom, Columbus Avenue at the top, 77th Street on the left.
Needs opencv-python-headless and numpy (only for this step).
"""
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / '.cache' / 'amnh'
PDF = CACHE / 'map.pdf'
URL = 'https://www.amnh.org/content/download/385996/5752508/file/english-map.pdf'
OUT = ROOT / 'tools' / 'data' / 'amnh-trace.json'
DEBUG = '--debug' in sys.argv
DPI = 200
PX = DPI / 72            # pixels per PDF point
PAGE = {'4': 2, '3': 3, '2': 4, '1': 5, 'LL': 6}
CROP = (20, 105, 560, 640)   # the plan, in points (below the legend)

# level: [room, kind, x, y] (PDF points): where each room starts growing
SEEDS = json.loads((ROOT / 'tools' / 'data' / 'amnh-seeds.json').read_text())
# areas (points) that are outside on every level: the front steps on Central Park West and the 81st Street sidewalk
OUTSIDE = [(295, 578, 560, 640), (515, 105, 560, 640)]
# lines (points) that close gaps in walls where the map leaves a door or exit open to the street
GAPS = {}


def u(v):
    return round(v * 2, 1)


def render(page):
    png = CACHE / f'p{page}.png'
    if not png.exists():
        subprocess.run(['pdftoppm', '-r', str(DPI), '-f', str(page), '-l', str(page), '-png', '-singlefile',
                        str(PDF), str(png)[:-4]], check=True)
    full = cv2.imread(str(png))
    x0, y0, x1, y1 = [int(v * PX) for v in CROP]
    return full[y0:y1, x0:x1]


def footprint():
    """The building's outline, the same on every page: a page's walls and grey, gaps closed, filled from outside.
    A page whose exits let the fill leak in loses some rooms, so the union over all pages is the footprint."""
    foot = None
    for page in PAGE.values():
        g = cv2.cvtColor(render(page), cv2.COLOR_BGR2GRAY).astype(int)
        h, w = g.shape
        shell = ((g < 120) | ((g > 180) & (g < 212))).astype(np.uint8)
        P = 60
        pad = cv2.copyMakeBorder(shell, P, P, P, P, cv2.BORDER_CONSTANT, value=0)
        closed = cv2.morphologyEx(pad, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (41, 41)))
        ff = closed.copy() * 255
        mask = np.zeros((h + 2 * P + 2, w + 2 * P + 2), np.uint8)
        cv2.floodFill(ff, mask, (0, 0), 128)
        inside = (ff[P:-P, P:-P] != 128).astype(np.uint8)
        inside = cv2.morphologyEx(inside, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25)))
        foot = inside if foot is None else (foot | inside)
    x0, y0 = [int(v * PX) for v in CROP[:2]]
    for (ax, ay, bx, by) in OUTSIDE:
        cv2.rectangle(foot, (int(ax * PX) - x0, int(ay * PX) - y0), (int(bx * PX) - x0, int(by * PX) - y0), 0, -1)
    return foot


# legend label -> amenity type (None: not shown)
ICON = {'Stairs': None, 'Elevator': 'elevator', 'Escalator': 'stairs', 'Restroom': 'restroom',
        'Family/All-Gender': 'restroom-all', 'Companion': 'restroom-all', 'Lactation': 'nursing', 'Dining': 'dining',
        'Shop': 'shop', 'Classroom': None, 'Ticket': 'ticket', 'Membership': None, 'Information': 'info',
        'ATM': None, 'Member': None, 'Storage': 'coat'}


def legend_words(page):
    out = subprocess.run(['pdftotext', '-f', str(page), '-l', str(page), '-bbox', str(PDF), '-'], capture_output=True,
                         text=True).stdout
    import re
    ws = re.findall(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="[\d.]+" yMax="[\d.]+">([^<]*)</word>', out)
    return [(float(x), float(y), w) for x, y, w in ws if 30 < float(y) < 80 and round(float(x)) in (58, 184, 328, 454, 455)]


def find_icons(page, c, x0, y0):
    """Amenity icons on the plan: each legend icon (and the single figures of the restroom pair) matched against it."""
    full = cv2.cvtColor(cv2.imread(str(CACHE / f'p{page}.png')), cv2.COLOR_BGR2GRAY)
    plan = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY)
    tpls = []
    for x, y, w in legend_words(page):
        kind = ICON.get(w)
        if not kind: continue
        ic = full[int((y - 1.5) * PX):int((y + 10) * PX), int((x - 23) * PX):int((x - 4) * PX)]
        ys, xs = np.nonzero(ic < 128)
        ic = ic[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        tpls.append((kind, ic, 0))
        if w == 'Restroom':                      # the pair, and each figure alone (woman left, man right)
            cols = np.nonzero((ic < 128).sum(0) == 0)[0]
            if len(cols):
                mid = int(np.median(cols))
                tpls.append(('restroom', ic[:, :mid], 1))
                tpls.append(('restroom', ic[:, mid:], 1))
        if w == 'Companion':                     # the wheelchair figure alone: an accessible restroom
            cols = np.nonzero((ic < 128).sum(0) == 0)[0]
            if len(cols):
                tpls.append(('restroom', ic[:, :int(cols.min())], 1))
    hits = []
    for kind, tpl, single in tpls:
        for sc in np.arange(0.8, 1.65, 0.1):
            tp = cv2.resize(tpl, None, fx=sc, fy=sc)
            if tp.shape[0] >= plan.shape[0] or tp.shape[1] < 8: continue
            r = cv2.matchTemplate(plan, tp, cv2.TM_CCOEFF_NORMED)
            yy, xx = np.nonzero(r > (0.8 if single else 0.74))
            for a, b in zip(xx, yy):
                hits.append((float(r[b, a]) - 0.05 * single, kind, a + tp.shape[1] / 2, b + tp.shape[0] / 2))
    hits.sort(key=lambda h: -h[0])
    keep = []
    for sc, kind, a, b in hits:
        near = 18 if kind != 'restroom' else 30
        if all((a - k[2]) ** 2 + (b - k[3]) ** 2 > near ** 2 for k in keep if k[1] == kind or
               {k[1], kind} <= {'restroom', 'restroom-all'}):
            keep.append((sc, kind, a, b))
    return [[kind, u((x0 + a) / PX), u((y0 + b) / PX)] for sc, kind, a, b in keep]


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    if not PDF.exists():
        subprocess.run(['curl', '-s', '-f', '-L', '-A', 'gallery-guide/1.0 (personal museum guide)', '-o', str(PDF), URL],
                       check=True)
    out = {}
    global FOOT
    FOOT = footprint()
    for lv, page in PAGE.items():
        c = render(page)
        x0, y0 = [int(v * PX) for v in CROP[:2]]
        g = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY).astype(int)
        h, w = g.shape
        dark = (g < 120).astype(np.uint8)
        grey = ((g > 180) & (g < 212)).astype(np.uint8)
        grey = cv2.morphologyEx(grey, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))   # hatching is not grey fill
        shell = ((dark + grey) > 0).astype(np.uint8)
        for (ax, ay, bx, by) in GAPS.get(lv, []):
            cv2.line(shell, (int(ax * PX) - x0, int(ay * PX) - y0), (int(bx * PX) - x0, int(by * PX) - y0), 1, 5)
        inside = FOOT
        markers = np.zeros((h, w), np.int32)
        markers[inside == 0] = 1
        markers[(grey == 1) & (inside == 1)] = 2
        names = ['__outside__', '__closed__']
        seeds = []
        for name, kind, x, y in SEEDS[lv]:
            if name not in names[2:]:
                names.append(name)
                seeds.append((name, kind, x, y))
            cv2.circle(markers, (int(x * PX) - x0, int(y * PX) - y0), 5, names.index(name) + 1, -1)
        img = np.full((h, w, 3), 255, np.uint8)
        img[dark > 0] = 0
        img[grey > 0] = 0
        img = cv2.GaussianBlur(img, (5, 5), 0)
        cv2.watershed(img, markers)
        lab = np.where(markers > 0, markers, 0).astype(np.uint16)
        for _ in range(60):
            need = (inside == 1) & (lab == 0)
            if not need.any(): break
            dil = cv2.dilate(lab, np.ones((3, 3), np.uint8))
            lab[need] = dil[need]
        lab[inside == 0] = 1
        markers = lab.astype(np.int32)

        def poly_of(m, eps=2.5):
            m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
            cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            return cs

        polys = {}
        vis = (c // 2 + 127).copy()
        rng = np.random.default_rng(3)
        cols = rng.integers(60, 230, (len(names) + 3, 3))
        ov = vis.copy()
        for i in range(3, len(names) + 1):
            ov[markers == i] = cols[i]
        vis = cv2.addWeighted(vis, 0.4, ov.astype(np.uint8), 0.6, 0)
        vis[dark > 0] = (0, 0, 0)
        for i, (name, kind, x, y) in enumerate(seeds):
            cs = poly_of(markers == i + 3)
            if not cs:
                print('missing', lv, name)
                continue
            cmax = max(cs, key=cv2.contourArea)
            ap = cv2.approxPolyDP(cmax, 2.5, True)[:, 0, :]
            polys[name] = [[u((x0 + p[0]) / PX), u((y0 + p[1]) / PX)] for p in ap]
            cv2.polylines(vis, [ap], True, (0, 0, 255), 1)
            cv2.putText(vis, name[:20], (int(x * PX) - x0 - 30, int(y * PX) - y0), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (0, 0, 160), 1)
        closed_polys = []
        cs = poly_of(markers == 2)
        for cc in cs:
            if cv2.contourArea(cc) < 300: continue
            ap = cv2.approxPolyDP(cc, 2.5, True)[:, 0, :]
            closed_polys.append([[u((x0 + p[0]) / PX), u((y0 + p[1]) / PX)] for p in ap])
        # doorways: where two rooms touch away from walls
        adj = {}
        for dy, dx in [(0, 6), (6, 0)]:
            a = markers[:h - dy, :w - dx]
            b = markers[dy:, dx:]
            ok = (a > 2) & (b > 2) & (a != b)
            ys, xs = np.nonzero(ok)
            for yy, xx in zip(ys, xs):
                k = tuple(sorted((int(a[yy, xx]), int(b[yy, xx]))))
                adj.setdefault(k, []).append((xx, yy))
        doors = []
        for (i, j), pts in adj.items():
            pts = [p for p in pts if dark[p[1], p[0]] == 0 and dark[min(h - 1, p[1] + 3), min(w - 1, p[0] + 3)] == 0]
            if len(pts) < 12: continue
            pts = np.array(pts)
            mx, my = pts.mean(0)
            k = ((pts - [mx, my]) ** 2).sum(1).argmin()
            px, py = pts[k]
            doors.append([names[i - 1], names[j - 1], u((x0 + px) / PX), u((y0 + py) / PX), len(pts)])
            cv2.circle(vis, (int(px), int(py)), 6, (0, 200, 0), -1)
        if DEBUG:
            cv2.imwrite(str(CACHE / f'trace-{lv}.png'), vis)
        icons = find_icons(page, c, x0, y0)
        if DEBUG:
            for kind, a, b in icons:
                cv2.putText(vis, kind[:5], (int(a / 2 * PX) - x0, int(b / 2 * PX) - y0), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                            (255, 0, 0), 2)
            cv2.imwrite(str(CACHE / f'trace-{lv}.png'), vis)
        out[lv] = {'icons': icons, 'polys': polys, 'closed': closed_polys, 'doors': doors,
                   'seeds': {name: [u(x), u(y)] for name, kind, x, y in seeds},
                   'kinds': {name: kind for name, kind, x, y in seeds}}
    OUT.write_text(json.dumps(out, ensure_ascii=False))
    for lv in out:
        print(lv, len(out[lv]['polys']), 'rooms', len(out[lv]['closed']), 'closed', len(out[lv]['doors']), 'doorways')


if __name__ == '__main__':
    main()
